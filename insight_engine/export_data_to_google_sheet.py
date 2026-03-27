"""Google Sheets export helpers for the insight engine dataframe."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from common.config import get_env


if TYPE_CHECKING:
    import pandas as pd


DEFAULT_WORKSHEET_NAME = "Sheet1"


def _load_gspread():
    try:
        import gspread
    except ImportError as exc:
        raise RuntimeError(
            "gspread is required for Google Sheets export. Install project dependencies first."
        ) from exc
    return gspread


def extract_spreadsheet_key(spreadsheet_id_or_url: str) -> str:
    """Accept a raw spreadsheet key or a full Google Sheets URL."""
    value = spreadsheet_id_or_url.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", value)
    if match:
        return match.group(1)
    return value


def get_google_sheets_client(service_account_json_path: str | None = None) -> Any:
    """Authenticate a gspread client from a service-account file."""
    gspread = _load_gspread()
    resolved_path = service_account_json_path or get_env(
        "GOOGLE_SERVICE_ACCOUNT_JSON_PATH",
        required=True,
    )

    try:
        return gspread.service_account(filename=resolved_path)
    except Exception as exc:
        raise RuntimeError(f"Google Sheets authentication failed: {exc}") from exc


def _worksheet_has_content(worksheet: Any) -> bool:
    try:
        values = worksheet.get_all_values()
    except Exception:
        return False

    return any(any(str(cell).strip() for cell in row) for row in values)


def _build_unique_worksheet_name(spreadsheet: Any, base_name: str) -> str:
    existing_titles = {worksheet.title for worksheet in spreadsheet.worksheets()}
    if base_name not in existing_titles:
        return base_name

    suffix = 2
    while True:
        candidate = f"{base_name}_{suffix}"
        if candidate not in existing_titles:
            return candidate
        suffix += 1


def _get_or_create_worksheet(spreadsheet: Any, worksheet_name: str) -> tuple[Any, str]:
    if worksheet_name == DEFAULT_WORKSHEET_NAME:
        worksheet = spreadsheet.sheet1
    else:
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except Exception:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=26)
            return worksheet, worksheet_name

    if not _worksheet_has_content(worksheet):
        return worksheet, worksheet.title

    new_worksheet_name = _build_unique_worksheet_name(spreadsheet, worksheet_name)
    new_worksheet = spreadsheet.add_worksheet(title=new_worksheet_name, rows=1000, cols=26)
    return new_worksheet, new_worksheet_name


def export_dataframe_to_google_sheet(
    dataframe: "pd.DataFrame",
    *,
    worksheet_name: str = DEFAULT_WORKSHEET_NAME,
    spreadsheet_id: str | None = None,
    service_account_json_path: str | None = None,
) -> str:
    """Write dataframe rows to an empty worksheet, creating a new sheet if needed."""
    resolved_spreadsheet_id = spreadsheet_id or get_env(
        "GOOGLE_SHEETS_SPREADSHEET_ID",
        required=True,
    )
    client = get_google_sheets_client(service_account_json_path=service_account_json_path)

    try:
        spreadsheet = client.open_by_key(extract_spreadsheet_key(resolved_spreadsheet_id))
        worksheet, resolved_worksheet_name = _get_or_create_worksheet(spreadsheet, worksheet_name)

        values = [list(dataframe.columns)]
        values.extend(dataframe.fillna("").astype(str).values.tolist())

        worksheet.update("A1", values)
    except Exception as exc:
        raise RuntimeError(f"Failed to export dataframe to Google Sheets: {exc}") from exc

    return (
        "Google Sheets export completed successfully "
        f"({len(dataframe)} rows, {len(dataframe.columns)} columns, worksheet: {resolved_worksheet_name})."
    )
