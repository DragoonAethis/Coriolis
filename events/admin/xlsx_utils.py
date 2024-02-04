import datetime
import decimal
import io
from pprint import pformat

import xlsxwriter
from django.http import FileResponse

XLSX_SAFE_TYPES = (
    bool,
    str,
    int,
    float,
    decimal.Decimal,
    datetime.date,
    datetime.time,
    datetime.datetime,
    datetime.timedelta,
)


def create_in_memory_xlsx() -> (io.BytesIO, xlsxwriter.Workbook, xlsxwriter.workbook.Worksheet):
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(
        buffer,
        {
            "in_memory": True,
            "strings_to_urls": False,
        },
    )

    return buffer, workbook, workbook.add_worksheet()


def finalize_in_memory_xlsx(
    buffer: io.BytesIO,
    workbook: xlsxwriter.Workbook,
    filename: str = "export.xlsx",
) -> FileResponse:
    workbook.close()
    buffer.seek(0)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    )


def xlsx_safe_value(value):
    if type(value) in XLSX_SAFE_TYPES:
        return value

    return pformat(value)
