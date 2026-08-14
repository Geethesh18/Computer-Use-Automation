import re
from typing import Any

from src.artifacts.models import (
    ActionType,
    CapabilityArtifact,
    Checkpoint,
    CheckpointType,
    Locator,
    ParameterType,
    Step,
)
from src.replay.models import ReplayResult, ReplayStatus
from src.surfaces.base import ComputerSurface


class ReplayEngine:
    """
    Deterministically executes a saved capability artifact.

    No LLM is used in this execution path.

    Replay supports:
    - typed input validation
    - parameter substitution
    - deterministic ordered execution
    - bounded retries for transient action failures
    - known business outcomes
    - known hard failures
    - checkpoint validation
    - typed output extraction
    - failure evidence capture
    """

    def __init__(
        self,
        surface: ComputerSurface,
        max_retries: int = 2,
    ):
        self.surface = surface
        self.max_retries = max_retries

    # =====================================================
    # Main replay
    # =====================================================

    def replay(
        self,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
    ) -> ReplayResult:

        # -------------------------------------------------
        # Validate invocation inputs before touching the UI
        # -------------------------------------------------

        input_error = self._validate_inputs(
            artifact,
            inputs,
        )

        if input_error:
            return ReplayResult(
                status=ReplayStatus.FAILURE,
                code="INVALID_INPUT",
                message=input_error,
                recoverable=False,
            )

        outputs: dict[str, Any] = {}

        try:
            # -------------------------------------------------
            # Start computer surface
            # -------------------------------------------------

            self.surface.start()

            # -------------------------------------------------
            # Navigate to deterministic entry point
            # -------------------------------------------------

            self.surface.navigate(
                artifact.entrypoint.url
            )

            # -------------------------------------------------
            # Execute artifact steps in order
            # -------------------------------------------------

            for step in artifact.steps:

                # Check whether the application is already
                # showing a known business/failure state.
                known_result = self._detect_known_state(
                    artifact,
                    step.id,
                )

                if known_result is not None:
                    return known_result

                # ---------------------------------------------
                # Execute with bounded deterministic retries
                # ---------------------------------------------

                execution_result = self._execute_with_retry(
                    step=step,
                    artifact=artifact,
                    inputs=inputs,
                    outputs=outputs,
                )

                if execution_result is not None:
                    return execution_result

                # ---------------------------------------------
                # Detect known state after successful action
                # ---------------------------------------------

                known_result = self._detect_known_state(
                    artifact,
                    step.id,
                )

                if known_result is not None:
                    return known_result

                # ---------------------------------------------
                # Verify step checkpoint
                # ---------------------------------------------

                if step.checkpoint is not None:

                    if not self._check(
                        step.checkpoint,
                        inputs,
                    ):
                        self._capture_failure(
                            step.id
                        )

                        expected_value = (
                            self._resolve_template(
                                step.checkpoint.value,
                                inputs,
                            )
                        )

                        return ReplayResult(
                            status=ReplayStatus.FAILURE,
                            code="CHECKPOINT_FAILED",
                            step_id=step.id,
                            expected=(
                                f"{step.checkpoint.type.value}: "
                                f"{expected_value}"
                            ),
                            observed=self._safe_visible_text(),
                            recoverable=False,
                        )

            # -------------------------------------------------
            # Verify final capability success condition
            # -------------------------------------------------

            if not self._check(
                artifact.success_condition,
                inputs,
            ):
                self._capture_failure(
                    "success_condition"
                )

                expected_value = (
                    self._resolve_template(
                        artifact.success_condition.value,
                        inputs,
                    )
                )

                return ReplayResult(
                    status=ReplayStatus.FAILURE,
                    code="SUCCESS_CONDITION_FAILED",
                    step_id="success_condition",
                    expected=(
                        f"{artifact.success_condition.type.value}: "
                        f"{expected_value}"
                    ),
                    observed=self._safe_visible_text(),
                    recoverable=False,
                )

            # -------------------------------------------------
            # Successful replay
            # -------------------------------------------------

            return ReplayResult(
                status=ReplayStatus.SUCCESS,
                outputs=outputs,
            )

        # -----------------------------------------------------
        # Unexpected replay-level failure
        # -----------------------------------------------------

        except Exception as exc:

            self._capture_failure(
                "replay"
            )

            return ReplayResult(
                status=ReplayStatus.FAILURE,
                code="REPLAY_FAILED",
                message=str(exc),
                observed=self._safe_visible_text(),
                recoverable=False,
            )

        finally:
            self.surface.stop()

    # =====================================================
    # Bounded retry execution
    # =====================================================

    def _execute_with_retry(
        self,
        step: Step,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> ReplayResult | None:
        """
        Execute one artifact step using a bounded retry policy.

        max_retries=2 means:

            attempt 1
            retry 1
            retry 2

        for a maximum of three attempts.

        No LLM is involved in recovery.

        Returns:
            None
                Step succeeded.

            ReplayResult
                Execution must stop because of a known
                outcome or an exhausted retry budget.
        """

        last_error: Exception | None = None
        total_attempts = self.max_retries + 1

        for attempt in range(
            1,
            total_attempts + 1,
        ):
            try:
                self._execute_step(
                    step=step,
                    artifact=artifact,
                    inputs=inputs,
                    outputs=outputs,
                )

                return None

            except Exception as exc:
                last_error = exc

                # -----------------------------------------
                # Did the application enter a known state?
                # -----------------------------------------

                known_result = self._detect_known_state(
                    artifact,
                    step.id,
                )

                if known_result is not None:
                    return known_result

                # -----------------------------------------
                # Retry only while budget remains
                # -----------------------------------------

                if attempt < total_attempts:
                    continue

                break

        # -------------------------------------------------
        # Retry budget exhausted
        # -------------------------------------------------

        self._capture_failure(
            step.id
        )

        return ReplayResult(
            status=ReplayStatus.FAILURE,
            code="STEP_EXECUTION_FAILED",
            step_id=step.id,
            message=(
                f"Step failed after "
                f"{total_attempts} attempts: "
                f"{last_error}"
            ),
            observed=self._safe_visible_text(),
            attempts=total_attempts,
            recoverable=False,
        )

    # =====================================================
    # Execute one artifact step
    # =====================================================

    def _execute_step(
        self,
        step: Step,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None:
        """
        Execute exactly one deterministic artifact action.

        This method performs no retries and contains no
        model reasoning.
        """

        # ---------------------------------------------
        # NAVIGATE
        # ---------------------------------------------

        if step.action == ActionType.NAVIGATE:

            url = self._resolve_value(
                step.value,
                inputs,
            )

            self.surface.navigate(
                str(url)
            )

            return

        # ---------------------------------------------
        # FILL
        # ---------------------------------------------

        if step.action == ActionType.FILL:

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

            return

        # ---------------------------------------------
        # CLICK
        # ---------------------------------------------

        if step.action == ActionType.CLICK:

            if step.target is None:
                raise ValueError(
                    "Click step requires a target."
                )

            self.surface.click(
                step.target
            )

            return

        # ---------------------------------------------
        # EXTRACT
        # ---------------------------------------------

        if step.action == ActionType.EXTRACT:

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

            return

        raise ValueError(
            f"Unsupported action: "
            f"{step.action}"
        )

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

            # ---------------------------------------------
            # STRING
            # ---------------------------------------------

            if (
                parameter.type == ParameterType.STRING
                and not isinstance(value, str)
            ):
                return (
                    f"Input '{parameter.name}' "
                    f"must be a string."
                )

            # ---------------------------------------------
            # NUMBER
            # ---------------------------------------------

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

            # ---------------------------------------------
            # BOOLEAN
            # ---------------------------------------------

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
    # Parameter substitution for action values
    # =====================================================

    def _resolve_value(
        self,
        value: Any,
        inputs: dict[str, Any],
    ) -> Any:
        """
        Resolve a value when the entire value is a
        parameter placeholder.

        Example:

            {{ member_id }}

        becomes:

            10002
        """

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
    # General template substitution
    # =====================================================

    def _resolve_template(
        self,
        value: str,
        inputs: dict[str, Any],
    ) -> str:
        """
        Resolve placeholders embedded anywhere in a string.

        Example:

            /members/{{ member_id }}/accounts

        becomes:

            /members/10002/accounts
        """

        resolved = value

        for name, input_value in inputs.items():

            resolved = resolved.replace(
                "{{ " + name + " }}",
                str(input_value),
            )

            # Also tolerate {{member_id}}
            resolved = resolved.replace(
                "{{" + name + "}}",
                str(input_value),
            )

        return resolved

    # =====================================================
    # Checkpoints
    # =====================================================

    def _check(
        self,
        checkpoint: Checkpoint,
        inputs: dict[str, Any] | None = None,
    ) -> bool:
        """
        Verify a checkpoint against the current UI state.

        Checkpoints may contain invocation parameters.
        """

        value = checkpoint.value

        if inputs:
            value = self._resolve_template(
                value,
                inputs,
            )

        # ---------------------------------------------
        # URL checkpoint
        # ---------------------------------------------

        if (
            checkpoint.type
            == CheckpointType.URL_CONTAINS
        ):
            return (
                value
                in self.surface.get_url()
            )

        # ---------------------------------------------
        # Text checkpoint
        # ---------------------------------------------

        if (
            checkpoint.type
            == CheckpointType.TEXT_PRESENT
        ):
            return (
                value
                in self.surface.get_visible_text()
            )

        # ---------------------------------------------
        # Element checkpoint
        # ---------------------------------------------

        if (
            checkpoint.type
            == CheckpointType.ELEMENT_PRESENT
        ):
            return (
                value
                in self.surface.get_visible_text()
            )

        return False

    # =====================================================
    # Known business outcomes and hard failures
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
                    recoverable=False,
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
                    recoverable=False,
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

        The mock legacy banking application exposes table
        rows in visible text similar to:

            Current Balance    $4520.75

        Depending on browser representation, label and
        value may appear either:

        1. On the same tab-separated line:

            Current Balance\\t$4520.75

        2. On consecutive lines:

            Current Balance
            $4520.75

        Both representations are supported.
        """

        # ---------------------------------------------
        # Explicit CSS extraction
        # ---------------------------------------------

        if target.css:
            return self.surface.extract_text(
                target
            )

        # ---------------------------------------------
        # Label-based extraction
        # ---------------------------------------------

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

                # -------------------------------------
                # Case 1:
                # Current Balance\t$4520.75
                # -------------------------------------

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

                # -------------------------------------
                # Case 2:
                #
                # Current Balance
                # $4520.75
                # -------------------------------------

                if line == target.text:

                    if index + 1 < len(lines):
                        return lines[
                            index + 1
                        ]

        # ---------------------------------------------
        # Final surface fallback
        # ---------------------------------------------

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
                if output.name == output_name
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