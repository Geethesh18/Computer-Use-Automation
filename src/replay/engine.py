import re
from typing import Any

from src.artifacts.models import (
    ActionType,
    CapabilityArtifact,
    Checkpoint,
    CheckpointType,
    Locator,
    ParameterType,
)
from src.replay.models import ReplayResult, ReplayStatus
from src.surfaces.base import ComputerSurface


class ReplayEngine:
    """
    Deterministically executes a saved capability artifact.

    No LLM is used in this execution path.
    """

    def __init__(self, surface: ComputerSurface):
        self.surface = surface

    def replay(
        self,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
    ) -> ReplayResult:

        # Validate invocation parameters before touching the UI.
        input_error = self._validate_inputs(
            artifact,
            inputs,
        )

        if input_error:
            return ReplayResult(
                status=ReplayStatus.FAILURE,
                code="INVALID_INPUT",
                message=input_error,
            )

        outputs: dict[str, Any] = {}

        try:
            self.surface.start()

            # Deterministic entry point.
            self.surface.navigate(
                artifact.entrypoint.url
            )

            for step in artifact.steps:

                # Detect known application states before proceeding.
                known_result = self._detect_known_state(
                    artifact,
                    step.id,
                )

                if known_result is not None:
                    return known_result

                try:
                    # ---------------------------------------------
                    # NAVIGATE
                    # ---------------------------------------------
                    if step.action == ActionType.NAVIGATE:
                        url = self._resolve_value(
                            step.value,
                            inputs,
                        )

                        self.surface.navigate(str(url))

                    # ---------------------------------------------
                    # FILL
                    # ---------------------------------------------
                    elif step.action == ActionType.FILL:
                        if step.target is None:
                            raise ValueError(
                                "Fill step requires a target."
                            )

                        value = self._resolve_value(
                            step.value,
                            inputs,
                        )

                        self.surface.fill(
                            step.target,
                            str(value),
                        )

                    # ---------------------------------------------
                    # CLICK
                    # ---------------------------------------------
                    elif step.action == ActionType.CLICK:
                        if step.target is None:
                            raise ValueError(
                                "Click step requires a target."
                            )

                        self.surface.click(
                            step.target
                        )

                    # ---------------------------------------------
                    # EXTRACT
                    # ---------------------------------------------
                    elif step.action == ActionType.EXTRACT:
                        if step.target is None:
                            raise ValueError(
                                "Extract step requires a target."
                            )

                        if step.output is None:
                            raise ValueError(
                                "Extract step requires an output name."
                            )

                        raw_value = self._extract_output(
                            step.target
                        )

                        outputs[step.output] = (
                            self._convert_output(
                                artifact,
                                step.output,
                                raw_value,
                            )
                        )

                    else:
                        raise ValueError(
                            f"Unsupported action: {step.action}"
                        )

                except Exception as exc:
                    # The action may have failed because the
                    # application entered a known business/failure
                    # state.

                    known_result = self._detect_known_state(
                        artifact,
                        step.id,
                    )

                    if known_result is not None:
                        return known_result

                    self._capture_failure(
                        step.id
                    )

                    return ReplayResult(
                        status=ReplayStatus.FAILURE,
                        code="STEP_EXECUTION_FAILED",
                        step_id=step.id,
                        message=str(exc),
                        observed=self._safe_visible_text(),
                    )

                # Check for known states immediately after an action.
                known_result = self._detect_known_state(
                    artifact,
                    step.id,
                )

                if known_result is not None:
                    return known_result

                # Verify step-level checkpoint.
                if step.checkpoint is not None:
                    if not self._check(
                        step.checkpoint
                    ):
                        self._capture_failure(
                            step.id
                        )

                        return ReplayResult(
                            status=ReplayStatus.FAILURE,
                            code="CHECKPOINT_FAILED",
                            step_id=step.id,
                            expected=(
                                f"{step.checkpoint.type.value}: "
                                f"{step.checkpoint.value}"
                            ),
                            observed=self._safe_visible_text(),
                        )

            # ---------------------------------------------
            # Final success condition
            # ---------------------------------------------

            if not self._check(
                artifact.success_condition
            ):
                self._capture_failure(
                    "success_condition"
                )

                return ReplayResult(
                    status=ReplayStatus.FAILURE,
                    code="SUCCESS_CONDITION_FAILED",
                    step_id="success_condition",
                    expected=(
                        f"{artifact.success_condition.type.value}: "
                        f"{artifact.success_condition.value}"
                    ),
                    observed=self._safe_visible_text(),
                )

            return ReplayResult(
                status=ReplayStatus.SUCCESS,
                outputs=outputs,
            )

        except Exception as exc:
            self._capture_failure(
                "replay"
            )

            return ReplayResult(
                status=ReplayStatus.FAILURE,
                code="REPLAY_FAILED",
                message=str(exc),
                observed=self._safe_visible_text(),
            )

        finally:
            self.surface.stop()

    # =====================================================
    # Input validation
    # =====================================================

    def _validate_inputs(
        self,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
    ) -> str | None:

        for parameter in artifact.inputs:

            if (
                parameter.required
                and parameter.name not in inputs
            ):
                return (
                    f"Missing required input: "
                    f"{parameter.name}"
                )

            if parameter.name not in inputs:
                continue

            value = inputs[
                parameter.name
            ]

            if (
                parameter.type == ParameterType.STRING
                and not isinstance(value, str)
            ):
                return (
                    f"Input '{parameter.name}' "
                    f"must be a string."
                )

            if (
                parameter.type == ParameterType.NUMBER
                and not isinstance(
                    value,
                    (int, float),
                )
            ):
                return (
                    f"Input '{parameter.name}' "
                    f"must be a number."
                )

            if (
                parameter.type == ParameterType.BOOLEAN
                and not isinstance(value, bool)
            ):
                return (
                    f"Input '{parameter.name}' "
                    f"must be a boolean."
                )

        return None

    # =====================================================
    # Parameter substitution
    # =====================================================

    def _resolve_value(
        self,
        value: Any,
        inputs: dict[str, Any],
    ) -> Any:

        if not isinstance(value, str):
            return value

        pattern = (
            r"^\{\{\s*"
            r"([a-zA-Z_][a-zA-Z0-9_]*)"
            r"\s*\}\}$"
        )

        match = re.match(
            pattern,
            value,
        )

        if not match:
            return value

        parameter_name = (
            match.group(1)
        )

        if parameter_name not in inputs:
            raise ValueError(
                f"Missing parameter: "
                f"{parameter_name}"
            )

        return inputs[
            parameter_name
        ]

    # =====================================================
    # Checkpoints
    # =====================================================

    def _check(
        self,
        checkpoint: Checkpoint,
    ) -> bool:

        if (
            checkpoint.type
            == CheckpointType.URL_CONTAINS
        ):
            return (
                checkpoint.value
                in self.surface.get_url()
            )

        if (
            checkpoint.type
            == CheckpointType.TEXT_PRESENT
        ):
            return (
                checkpoint.value
                in self.surface.get_visible_text()
            )

        if (
            checkpoint.type
            == CheckpointType.ELEMENT_PRESENT
        ):
            return (
                checkpoint.value
                in self.surface.get_visible_text()
            )

        return False

    # =====================================================
    # Known business outcomes and failures
    # =====================================================

    def _detect_known_state(
        self,
        artifact: CapabilityArtifact,
        step_id: str,
    ) -> ReplayResult | None:

        # ---------------------------------------------
        # Expected business outcomes
        # ---------------------------------------------

        for outcome in artifact.business_outcomes:

            if self._check(
                outcome.detect
            ):
                return ReplayResult(
                    status=ReplayStatus.BUSINESS_OUTCOME,
                    code=outcome.code,
                    step_id=step_id,
                    message=outcome.description,
                )

        # ---------------------------------------------
        # Known hard failures
        # ---------------------------------------------

        for failure in artifact.failure_conditions:

            if self._check(
                failure.detect
            ):
                self._capture_failure(
                    step_id
                )

                return ReplayResult(
                    status=ReplayStatus.FAILURE,
                    code=failure.code,
                    step_id=step_id,
                    message=failure.description,
                    observed=self._safe_visible_text(),
                )

        return None

    # =====================================================
    # Output extraction
    # =====================================================

    def _extract_output(
        self,
        target: Locator,
    ) -> str:
        """
        Extract a value associated with a target label.

        The mock legacy banking application uses table rows
        that Playwright exposes as visible text similar to:

            Current Balance    $4520.75

        Depending on the browser representation, the label
        and value may appear either:

        1. On the same tab-separated line:

            Current Balance\\t$4520.75

        2. On consecutive lines:

            Current Balance
            $4520.75

        Both representations are supported.
        """

        # If the artifact explicitly provides a CSS locator,
        # use the surface directly.
        if target.css:
            return self.surface.extract_text(
                target
            )

        if target.text:
            visible_text = (
                self.surface.get_visible_text()
            )

            lines = [
                line.strip()
                for line
                in visible_text.splitlines()
                if line.strip()
            ]

            for index, line in enumerate(lines):

                # -----------------------------------------
                # Case 1:
                #
                # Current Balance\t$4520.75
                # -----------------------------------------

                if "\t" in line:
                    parts = [
                        part.strip()
                        for part
                        in line.split("\t")
                        if part.strip()
                    ]

                    if (
                        len(parts) >= 2
                        and parts[0] == target.text
                    ):
                        return parts[1]

                # -----------------------------------------
                # Case 2:
                #
                # Current Balance
                # $4520.75
                # -----------------------------------------

                if line == target.text:
                    if index + 1 < len(lines):
                        return lines[
                            index + 1
                        ]

        # Final fallback to normal surface extraction.
        return self.surface.extract_text(
            target
        )

    # =====================================================
    # Output type conversion
    # =====================================================

    def _convert_output(
        self,
        artifact: CapabilityArtifact,
        output_name: str,
        raw_value: str,
    ) -> Any:

        definition = next(
            (
                output
                for output
                in artifact.outputs
                if output.name
                == output_name
            ),
            None,
        )

        if definition is None:
            raise ValueError(
                f"Unknown output: "
                f"{output_name}"
            )

        # ---------------------------------------------
        # STRING
        # ---------------------------------------------

        if (
            definition.type
            == ParameterType.STRING
        ):
            return raw_value.strip()

        # ---------------------------------------------
        # NUMBER
        # ---------------------------------------------

        if (
            definition.type
            == ParameterType.NUMBER
        ):
            cleaned = re.sub(
                r"[^0-9.\-]",
                "",
                raw_value,
            )

            if not cleaned:
                raise ValueError(
                    f"Could not parse number "
                    f"from '{raw_value}'."
                )

            return float(
                cleaned
            )

        # ---------------------------------------------
        # BOOLEAN
        # ---------------------------------------------

        if (
            definition.type
            == ParameterType.BOOLEAN
        ):
            normalized = (
                raw_value
                .strip()
                .lower()
            )

            if normalized in {
                "true",
                "yes",
                "1",
            }:
                return True

            if normalized in {
                "false",
                "no",
                "0",
            }:
                return False

            raise ValueError(
                f"Could not parse boolean "
                f"from '{raw_value}'."
            )

        return raw_value

    # =====================================================
    # Failure evidence
    # =====================================================

    def _capture_failure(
        self,
        step_id: str,
    ) -> None:

        safe_step_id = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            step_id,
        )

        try:
            self.surface.screenshot(
                (
                    "evidence/"
                    f"replay_failure_"
                    f"{safe_step_id}.png"
                )
            )

        except Exception:
            # Evidence collection must never hide
            # the original replay failure.
            pass

    def _safe_visible_text(
        self,
    ) -> str | None:

        try:
            return (
                self.surface
                .get_visible_text()
            )

        except Exception:
            return None