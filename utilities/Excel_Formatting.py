from pandas.io.excel._xlsxwriter import XlsxWriter
from flask import jsonify
import re
import io
import pandas as pd
import logging

from .Azure_Translator import Translator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_excel_with_formatting_local(df, language, sheet_name):
    """
    Creates an Excel file with specific formatting for a DataFrame.
    - Text-wraps the "Query" column and bolds text within <b>bold</b> markers.
    - Sets column widths for readability.
    - Applies header formatting for clarity.

    Args:
        df: The DataFrame to be formatted.
        language: Language for translating headers.
        sheet_name: The name of the worksheet to create.

    Returns:
        A byte string containing the formatted Excel file.
    """
    # Set up the output for Excel writing
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # Define formats
    bold_format = workbook.add_format({'bold': True})
    top_aligned_format = workbook.add_format({"text_wrap": True, "valign": "top"})
    header_format = workbook.add_format({
        "bold": True,
        "text_wrap": True,
        "valign": "top",
        "fg_color": "#ADD8E6",
        "border": 1,
        "align": "center"
    })

    # Add worksheet and set column widths
    df.to_excel(writer, sheet_name=sheet_name, startrow=1, header=False, index=False)
    worksheet = writer.sheets[sheet_name]
    worksheet.set_column(0, 0, 10)  # Serial No column
    worksheet.set_column(1, 1, 40, top_aligned_format)  # Contract Terms column
    worksheet.set_column(2, 2, 50, top_aligned_format)  # Query column
    worksheet.set_column(3, 3, 100, top_aligned_format)  # AI Response column

    # Translate and write headers
    translator = Translator()
    for col_num, value in enumerate(df.columns.values):
        translated_value = translator.translate(value, language)
        worksheet.write(0, col_num, translated_value, header_format)

    # Function to format "Query" and "AI Response" columns with bold text inside <b> and </b> markers
    def write_formatted_cell(row, col, value):
        # Convert **text** to <b>text</b> for compatibility
        value = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', value)
        
        # Split the value based on <b> and </b> tags
        parts = re.split(r'(<b>|</b>)', value)
        formatted_parts = []

        bold_text = False  # Flag to apply bold format
        for part in parts:
            if part == '<b>':
                bold_text = True
            elif part == '</b>':
                bold_text = False
            elif part:  # If the part is not empty
                if bold_text:
                    formatted_parts.append(bold_format)
                    formatted_parts.append(part)
                else:
                    formatted_parts.append(part)
        
        # Write formatted text to cell
        if formatted_parts:
            worksheet.write_rich_string(row, col, *formatted_parts, top_aligned_format)
        else:
            worksheet.write(row, col, value, top_aligned_format)

    # Write DataFrame contents with formatting applied to specific columns
    for row_num in range(1, len(df) + 1):
        for col_num in range(len(df.columns)):
            if col_num in [2, 3]:  # Assuming "Query" and "AI Response" columns are at index 2 and 3
                write_formatted_cell(row_num, col_num, str(df.iloc[row_num - 1, col_num]))
            else:
                worksheet.write(row_num, col_num, str(df.iloc[row_num - 1, col_num]), top_aligned_format)

    # Close the writer and return the file as a byte string
    writer.close()
    output.seek(0)
    return output.getvalue()