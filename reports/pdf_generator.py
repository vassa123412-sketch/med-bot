"""
PDF Report Generator with charts and medical analysis
"""
import os
import logging
from datetime import datetime
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

logger = logging.getLogger(__name__)

# Register Arial fonts for Cyrillic support
try:
    windir = os.environ.get('SystemRoot', 'C:/Windows')
    font_dir = os.path.join(windir, 'Fonts')
    # Define font files
    font_files = [
        ('Arial', os.path.join(font_dir, 'arial.ttf')),
        ('ArialBold', os.path.join(font_dir, 'arialbd.ttf')),
        ('ArialItalic', os.path.join(font_dir, 'ariali.ttf')),
        ('ArialBoldItalic', os.path.join(font_dir, 'arialbi.ttf'))
    ]
    # Register each font
    for font_name, font_path in font_files:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            logger.debug(f"Registered font '{font_name}' from {font_path}")
        else:
            logger.warning(f"Font file not found: {font_path}")
    logger.info("Arial fonts registration attempted")
except Exception as e:
    logger.warning(f'Failed to register Arial fonts: {e}. Falling back to default fonts.')

# Set matplotlib font to support Cyrillic
plt.rcParams['font.family'] = 'Arial'
plt.rcParams['font.size'] = 10

REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CHARTS_DIR = Path("data/charts")
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def create_symptom_chart(symptoms_data: dict, output_path: str):
    """Create a symptom analysis chart"""
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    
    # Symptom severity bar chart
    symptoms = symptoms_data.get('symptoms', []) or []
    severity = symptoms_data.get('severity', []) or []
    urgency = symptoms_data.get('urgency', 'Средний')
    
    if symptoms and severity and len(symptoms) == len(severity):
        # Sort by severity for better visualization
        sorted_data = sorted(zip(symptoms, severity), key=lambda x: x[1])
        symptoms_sorted, severity_sorted = zip(*sorted_data) if sorted_data else ([], [])
        
        # Create horizontal bar chart
        y_pos = np.arange(len(symptoms_sorted))
        bars = ax.barh(y_pos, severity_sorted, color='#648FFF', edgecolor='black', linewidth=0.5)
        
        # Customize the chart
        ax.set_yticks(y_pos)
        ax.set_yticklabels(symptoms_sorted, fontsize=10)
        ax.set_xlabel('Степень выраженности', fontsize=12, fontweight='bold')
        ax.set_title('Анализ симптомов по степени выраженности', fontsize=14, fontweight='bold', pad=20)
        ax.set_xlim(0, 10)
        
        # Add value labels on bars
        for i, (bar, severity_val) in enumerate(zip(bars, severity_sorted)):
            width = bar.get_width()
            ax.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
                   f'{severity_val:.0f}', ha='left', va='center', fontweight='bold')
        
        # Add urgency indicator as a colored bar at the bottom
        urgency_colors = {
            'Высокий': '#FF6B6B',
            'Средний': '#FFB000',
            'Низкий': '#3FB950'
        }
        urgency_color = urgency_colors.get(urgency, '#648FFF')
        
        # Add a colored rectangle to indicate urgency level
        from matplotlib.patches import Rectangle
        urgency_rect = Rectangle((0, -0.5), 10, 0.3, 
                               transform=ax.get_yaxis_transform(),
                               color=urgency_color, alpha=0.3, 
                               label=f'Уровень срочности: {urgency}')
        ax.add_patch(urgency_rect)
        
        # Add legend for urgency
        ax.legend(loc='lower right', frameon=True, fancybox=True, shadow=True)
        
    else:
        # No data case
        ax.text(0.5, 0.5, 'Недостаточно данных для визуализации', 
               ha='center', va='center', fontsize=14, 
               transform=ax.transAxes, color='gray')
        ax.set_title('Анализ симптомов', fontsize=14, fontweight='bold', pad=20)
        ax.set_xticks([])
        ax.set_yticks([])
    
    # Improve layout
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    return output_path


def create_pdf_report(
    user_name: str,
    symptoms: str,
    analysis_result: str,
    triage_level: str = "Средний",
    recommendations: list = None,
    include_chart: bool = True
) -> str:
    """Generate a PDF report from symptom analysis"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.pdf"
    filepath = REPORTS_DIR / filename
    
    # Create chart if requested
    chart_path = None
    if include_chart:
        chart_path = str(CHARTS_DIR / f"chart_{timestamp}.png")
        symptom_list = [s.strip() for s in symptoms.replace(',', ' ').split() if len(s.strip()) > 3][:5]
        severity = [max(8 - i, 1) for i in range(len(symptom_list))]
        symptoms_data = {
            'symptoms': symptom_list,
            'severity': severity,
            'urgency': triage_level
        }
        create_symptom_chart(symptoms_data, chart_path)
    
    # Create PDF
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Title'],
        fontName='ArialBold',
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10,
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='CustomHeading',
        parent=styles['Heading2'],
        fontName='ArialBold',
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceBefore=15,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['BodyText'],
        fontName='Arial',
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='Disclaimer',
        parent=styles['BodyText'],
        fontName='Arial',
        fontSize=8,
        textColor=colors.HexColor('#e74c3c'),
        leading=12,
        alignment=TA_CENTER,
        spaceBefore=20
    ))
    
    story = []
    
    # Header
    story.append(Paragraph("МЕДАССИСТЕНТ", styles['CustomTitle']))
    story.append(Paragraph("Отчёт анализа симптомов", styles['CustomTitle']))
    story.append(Spacer(1, 0.5*cm))
    
    # Info table
    info_data = [
        ['Дата', datetime.now().strftime("%d.%m.%Y %H:%M")],
        ['Пациент', user_name],
        ['Уровень срочности', triage_level],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2c3e50')),
        ('FONTNAME', (0, 0), (0, -1), 'ArialBold'),
        ('FONTNAME', (1, 0), (1, -1), 'Arial'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
        ('BOX' , (0, 0), (-1, -1), 2, colors.HexColor('#34495e')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 1*cm))
    
    # Symptoms
    story.append(Paragraph("Описание симптомов", styles['CustomHeading']))
    story.append(Paragraph(symptoms, styles['CustomBody']))
    story.append(Spacer(1, 0.3*cm))
    
    # Chart
    if chart_path and os.path.exists(chart_path):
        story.append(Paragraph("Визуализация", styles['CustomHeading']))
        img = Image(chart_path, width=14*cm, height=6*cm)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Spacer(1, 0.3*cm))
    
    # Analysis
    story.append(Paragraph("Результат анализа", styles['CustomHeading']))
    # Clean up markdown and filter out unwanted text for PDF
    import re
    clean_text = re.sub(r'[*_#`>`()\[\]]', '', analysis_result)
    # Filter out lines containing developer signatures or unwanted content
    unwanted_patterns = [
        r'Ivan_Zadov',
        r'разработка Telegram-ботов',
        r'@Ivan_Zadov',
        r'разработка ботов'
    ]
    for line in clean_text.split('\n'):
        line = line.strip()
        if line:
            # Check if line contains any unwanted patterns
            skip_line = False
            for pattern in unwanted_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    skip_line = True
                    break
            if not skip_line:
                story.append(Paragraph(line, styles['CustomBody']))
    
    # Recommendations
    if recommendations:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("Рекомендации", styles['CustomHeading']))
        for i, rec in enumerate(recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", styles['CustomBody']))
    
    # Disclaimer
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "⚠️ ВНИМАНИЕ: Данный отчёт носит исключительно информационный характер.\n"
        "Он НЕ является медицинским диагнозом и НЕ заменяет консультацию врача.\n"
        "Обратитесь к квалифицированному специалисту для точной диагностики и лечения.",
        styles['Disclaimer']
    ))
    
    # Build PDF
    doc.build(story)
    logger.info(f"PDF report generated: {filepath}")
    return str(filepath)


def create_lab_pdf_report(
    user_name: str,
    ocr_text: str,
    analysis_result: str,
) -> str:
    """Generate a PDF report from lab results analysis"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"lab_report_{timestamp}.pdf"
    filepath = REPORTS_DIR / filename

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Title'],
        fontName='ArialBold',
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10,
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='CustomHeading',
        parent=styles['Heading2'],
        fontName='ArialBold',
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceBefore=15,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['BodyText'],
        fontName='Arial',
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='OcrText',
        parent=styles['BodyText'],
        fontName='Arial',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='Disclaimer',
        parent=styles['BodyText'],
        fontName='Arial',
        fontSize=8,
        textColor=colors.HexColor('#e74c3c'),
        leading=12,
        alignment=TA_CENTER,
        spaceBefore=20
    ))

    story = []

    story.append(Paragraph("МЕДАССИСТЕНТ", styles['CustomTitle']))
    story.append(Paragraph("Расшифровка лабораторных анализов", styles['CustomTitle']))
    story.append(Spacer(1, 0.5*cm))

    info_data = [
        ['Дата', datetime.now().strftime("%d.%m.%Y %H:%M")],
        ['Пациент', user_name],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2c3e50')),
        ('FONTNAME', (0, 0), (0, -1), 'ArialBold'),
        ('FONTNAME', (1, 0), (1, -1), 'Arial'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
        ('BOX' , (0, 0), (-1, -1), 2, colors.HexColor('#34495e')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Распознанный текст с бланка", styles['CustomHeading']))
    import re
    for line in ocr_text.split('\n'):
        line = line.strip()
        if line:
            story.append(Paragraph(line, styles['OcrText']))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Результат расшифровки", styles['CustomHeading']))
    clean_text = re.sub(r'[*_#`>`()\[\]]', '', analysis_result)
    for line in clean_text.split('\n'):
        line = line.strip()
        if line:
            story.append(Paragraph(line, styles['CustomBody']))

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "⚠️ ВНИМАНИЕ: Данный отчёт носит исключительно информационный характер.\n"
        "Он НЕ является медицинским диагнозом и НЕ заменяет консультацию врача.\n"
        "Обратитесь к квалифицированному специалисту для точной диагностики и лечения.",
        styles['Disclaimer']
    ))

    doc.build(story)
    logger.info(f"Lab PDF report generated: {filepath}")
    return str(filepath)