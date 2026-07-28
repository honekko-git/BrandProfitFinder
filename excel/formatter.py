"""
Excel formatting helpers.
"""

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")


def format_header_row(sheet: Worksheet, column_count: int) -> None:
    """
    Apply header styling to the first row.

    Args:
        sheet: Target worksheet.
        column_count: Number of columns to style.
    """
    for col in range(1, column_count + 1):
        cell = sheet.cell(row=1, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT


def auto_fit_columns(sheet: Worksheet, max_width: int = 50) -> None:
    """
    Adjust column widths based on cell content.

    Args:
        sheet: Target worksheet.
        max_width: Maximum column width cap.
    """
    for column_cells in sheet.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        adjusted = min(max(length + 2, 10), max_width)
        sheet.column_dimensions[column_cells[0].column_letter].width = adjusted
