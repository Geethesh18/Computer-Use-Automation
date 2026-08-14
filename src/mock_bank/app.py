from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.mock_bank.data import MEMBERS


# ---------------------------------------------------------
# Application configuration
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

app = FastAPI(
    title="Mock Legacy Banking Application",
    description="Local banking application for computer-use automation testing",
    version="1.0.0",
)


# ---------------------------------------------------------
# Member Search
# ---------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Display the member search page.
    """

    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={},
    )


@app.post("/members/search")
def search_member(member_id: str = Form(...)):
    """
    Accept a member ID from the search form and redirect
    to the corresponding member details page.
    """

    member_id = member_id.strip()

    return RedirectResponse(
        url=f"/members/{member_id}",
        status_code=303,
    )


# ---------------------------------------------------------
# Member Details
# ---------------------------------------------------------

@app.get(
    "/members/{member_id}",
    response_class=HTMLResponse,
)
def member_details(
    request: Request,
    member_id: str,
):
    """
    Display basic information for a member.

    If the member does not exist, return the
    MEMBER_NOT_FOUND business outcome.
    """

    member = MEMBERS.get(member_id)

    if member is None:
        return templates.TemplateResponse(
            request=request,
            name="member_not_found.html",
            context={
                "member_id": member_id,
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="member_details.html",
        context={
            "member": member,
        },
    )


# ---------------------------------------------------------
# Member Accounts
# ---------------------------------------------------------

@app.get(
    "/members/{member_id}/accounts",
    response_class=HTMLResponse,
)
def member_accounts(
    request: Request,
    member_id: str,
):
    """
    Display all accounts belonging to a member.

    Restricted members are not permitted to access
    account information.
    """

    member = MEMBERS.get(member_id)

    # Member does not exist
    if member is None:
        return templates.TemplateResponse(
            request=request,
            name="member_not_found.html",
            context={
                "member_id": member_id,
            },
            status_code=404,
        )

    # Simulated permission-denied runtime condition
    if member["status"] == "Restricted":
        return templates.TemplateResponse(
            request=request,
            name="permission_denied.html",
            context={
                "member": member,
            },
            status_code=403,
        )

    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={
            "member": member,
        },
    )


# ---------------------------------------------------------
# Individual Account Details
# ---------------------------------------------------------

@app.get(
    "/members/{member_id}/accounts/{account_key}",
    response_class=HTMLResponse,
)
def account_details(
    request: Request,
    member_id: str,
    account_key: str,
):
    """
    Display information for a specific account,
    including its current balance.
    """

    member = MEMBERS.get(member_id)

    # Member does not exist
    if member is None:
        return templates.TemplateResponse(
            request=request,
            name="member_not_found.html",
            context={
                "member_id": member_id,
            },
            status_code=404,
        )

    # Prevent restricted members from bypassing
    # the accounts page by navigating directly to
    # an account URL.
    if member["status"] == "Restricted":
        return templates.TemplateResponse(
            request=request,
            name="permission_denied.html",
            context={
                "member": member,
            },
            status_code=403,
        )

    account = member["accounts"].get(account_key)

    # Requested account does not exist
    if account is None:
        return HTMLResponse(
            content="Account not found",
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="account_details.html",
        context={
            "member": member,
            "account": account,
        },
    )