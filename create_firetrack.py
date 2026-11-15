
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.dml import MSO_LINE_DASH_STYLE
import math

# =====================================================
# FIRETRACK - NASA SPACE APPS CHALLENGE 2026
# 7-SLIDE PROJECT DEMO PRESENTATION
# =====================================================

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# Theme
BG = RGBColor(7, 17, 35)
PANEL = RGBColor(15, 31, 56)
PANEL2 = RGBColor(20, 42, 70)
WHITE = RGBColor(240, 246, 255)
MUTED = RGBColor(160, 180, 205)
CYAN = RGBColor(54, 205, 225)
ORANGE = RGBColor(255, 135, 55)
RED = RGBColor(245, 75, 65)
GREEN = RGBColor(90, 205, 145)
YELLOW = RGBColor(245, 195, 75)

FONT = "Aptos"

# -----------------------------------------------------
# BASIC HELPERS
# -----------------------------------------------------

def add_bg(slide):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0,
        prs.slide_width, prs.slide_height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = BG
    shape.line.fill.background()

    # Decorative top line
    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0, 0, prs.slide_width, Inches(0.055)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = CYAN
    line.line.fill.background()


def add_text(slide, text, x, y, w, h,
             size=18, color=WHITE, bold=False,
             align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.alignment = align
    p.space_after = Pt(4)

    r = p.add_run()
    r.text = text
    r.font.name = FONT
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color

    return box


def add_rect(slide, x, y, w, h, color,
             radius=False, line_color=None):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        kind, Inches(x), Inches(y),
        Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color

    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()

    return shape


def add_circle(slide, x, y, diameter, color):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(x), Inches(y),
        Inches(diameter), Inches(diameter)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_line(slide, x1, y1, x2, y2, color=CYAN, width=2):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1), Inches(y1),
        Inches(x2), Inches(y2)
    )
    line.line.color.rgb = color
    line.line.width = Pt(width)
    return line


def add_header(slide, number, title, subtitle=None):
    add_text(slide, f"FIRETRACK  /  NASA SPACE APPS 2026",
             0.55, 0.25, 8, 0.3, 10, CYAN, True)
    add_text(slide, f"{number:02d} / 07",
             11.6, 0.25, 1.1, 0.3, 10, MUTED, True,
             PP_ALIGN.RIGHT)
    add_text(slide, title, 0.65, 0.8, 12, 0.65,
             29, WHITE, True)
    if subtitle:
        add_text(slide, subtitle, 0.68, 1.48, 11.8, 0.45,
                 13, MUTED)


def add_footer(slide):
    add_line(slide, 0.65, 7.05, 12.68, 7.05, PANEL2, 1)
    add_text(slide, "FIRETRACK  |  Exploring satellite fire data",
             0.7, 7.12, 8, 0.2, 8, MUTED)


def add_card(slide, x, y, w, h, title, body,
             accent=CYAN):
    add_rect(slide, x, y, w, h, PANEL, True)
    add_rect(slide, x, y, 0.055, h, accent)
    add_text(slide, title, x + 0.22, y + 0.2,
             w - 0.4, 0.4, 16, accent, True)
    add_text(slide, body, x + 0.22, y + 0.72,
             w - 0.4, h - 0.85, 12, WHITE)


def add_bullet(slide, text, x, y, width=5.5,
               color=WHITE, bullet_color=CYAN):
    add_circle(slide, x, y + 0.09, 0.11, bullet_color)
    add_text(slide, text, x + 0.25, y,
             width, 0.42, 15, color)


def new_slide():
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    return slide


# =====================================================
# SLIDE 1 - INTRODUCTION
# =====================================================

slide = new_slide()

add_text(slide, "NASA SPACE APPS CHALLENGE 2026",
         0.85, 0.8, 8, 0.4, 13, CYAN, True)

add_text(slide, "FIRETRACK",
         0.8, 1.55, 7.2, 1.0, 48, WHITE, True)

add_text(slide,
         "Exploring Fire Activity Through Satellite Data",
         0.88, 2.65, 7.2, 0.8, 22, ORANGE, True)

add_text(slide,
         "A web-based platform designed to explore and analyse "
         "MODIS and VIIRS active-fire hotspot information.",
         0.9, 3.65, 6.3, 1.0, 17, MUTED)

# Satellite-inspired illustration
add_circle(slide, 9.1, 1.5, 2.4, PANEL2)
add_circle(slide, 9.65, 2.05, 1.3, CYAN)
add_rect(slide, 8.0, 2.25, 1.0, 0.8, CYAN)
add_rect(slide, 10.9, 2.25, 1.0, 0.8, CYAN)
add_line(slide, 10.25, 2.7, 10.7, 2.7, WHITE, 3)

# Satellite signal rings
for d in [2.9, 3.6]:
    ring = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(10.3 - d/2), Inches(2.7 - d/2),
        Inches(d), Inches(d)
    )
    ring.fill.background()
    ring.line.color.rgb = PANEL2
    ring.line.width = Pt(1.5)

add_text(slide, "MODIS  +  VIIRS",
         8.3, 4.6, 4.0, 0.5, 17, CYAN, True,
         PP_ALIGN.CENTER)

add_text(slide,
         "CHALLENGE: Harmonization of MODIS and VIIRS Hot Spots",
         0.9, 6.2, 10.8, 0.4, 13, MUTED)

add_footer(slide)


# =====================================================
# SLIDE 2 - THE PROBLEM
# =====================================================

slide = new_slide()
add_header(slide, 2, "The Problem",
           "Understanding satellite fire information can be challenging.")

problems = [
    ("01", "Different datasets",
     "Exploring MODIS and VIIRS information together can be difficult."),
    ("02", "Geographical context",
     "Users need to understand hotspot activity within selected areas."),
    ("03", "Historical patterns",
     "Comparing activity across dates and periods requires analysis."),
    ("04", "Data uncertainty",
     "Missing data and incomplete coverage can be misunderstood.")
]

positions = [
    (0.8, 2.2), (6.8, 2.2),
    (0.8, 4.25), (6.8, 4.25)
]

for (num, title, body), (x, y) in zip(problems, positions):
    add_rect(slide, x, y, 5.65, 1.55, PANEL, True)
    add_text(slide, num, x + 0.25, y + 0.25,
             0.65, 0.5, 23, ORANGE, True)
    add_text(slide, title, x + 1.05, y + 0.2,
             4.2, 0.4, 17, CYAN, True)
    add_text(slide, body, x + 1.05, y + 0.72,
             4.25, 0.65, 12, WHITE)

add_footer(slide)


# =====================================================
# SLIDE 3 - OUR APPROACH
# =====================================================

slide = new_slide()
add_header(slide, 3, "Our Approach",
           "One interface for exploring satellite hotspot information.")

steps = [
    ("01", "SELECT AOI", "Choose an Area of Interest."),
    ("02", "EXPLORE DATA", "Explore MODIS and VIIRS records."),
    ("03", "ANALYSE", "Compare spatial and temporal patterns."),
    ("04", "INTERPRET", "Review data availability and limitations.")
]

for i, (num, title, body) in enumerate(steps):
    x = 0.8 + i * 3.1
    add_rect(slide, x, 2.6, 2.65, 2.0, PANEL, True)
    add_circle(slide, x + 0.95, 2.15, 0.7, CYAN)
    add_text(slide, num, x + 1.02, 2.32,
             0.55, 0.25, 13, BG, True,
             PP_ALIGN.CENTER)
    add_text(slide, title, x + 0.2, 3.0,
             2.25, 0.45, 15, CYAN, True,
             PP_ALIGN.CENTER)
    add_text(slide, body, x + 0.2, 3.65,
             2.25, 0.7, 12, WHITE,
             align=PP_ALIGN.CENTER)

    if i < 3:
        add_line(slide, x + 2.68, 3.55,
                 x + 3.0, 3.55, ORANGE, 2)

add_text(slide,
         "Focus: geographical exploration • time-based analysis • transparency",
         1.1, 5.5, 11, 0.5, 16, MUTED, True,
         PP_ALIGN.CENTER)

add_footer(slide)


# =====================================================
# SLIDE 4 - MAIN FEATURES
# =====================================================

slide = new_slide()
add_header(slide, 4, "Main Features",
           "Project feature areas — demonstrate only what is verified.")

features = [
    ("AOI EXPLORATION", "Explore hotspot records for a selected area."),
    ("ACTIVITY CALENDAR", "View records across dates."),
    ("HISTORICAL ANALYTICS", "Explore historical activity patterns."),
    ("SENSOR COMPARISON", "Compare MODIS and VIIRS records."),
    ("SPATIAL VISUALISATION", "Explore geographical hotspot locations."),
    ("ANOMALY EXPLORER", "Explore unusual patterns where data is sufficient.")
]

for i, (title, body) in enumerate(features):
    col = i % 3
    row = i // 3
    x = 0.75 + col * 4.2
    y = 2.15 + row * 1.85
    accent = [CYAN, ORANGE, GREEN][col]
    add_card(slide, x, y, 3.8, 1.5, title, body, accent)

add_text(slide,
         "Feature availability and results depend on verified data and working application components.",
         0.9, 6.25, 11.7, 0.45, 11, YELLOW, True,
         PP_ALIGN.CENTER)

add_footer(slide)


# =====================================================
# SLIDE 5 - DATA AND METHODOLOGY
# =====================================================

slide = new_slide()
add_header(slide, 5, "Data and Methodology",
           "Exploring NASA satellite active-fire hotspot products.")

# Data source panels
add_card(slide, 0.8, 2.0, 3.5, 1.55,
         "MODIS", "Moderate Resolution Imaging Spectroradiometer",
         CYAN)

add_card(slide, 4.9, 2.0, 3.5, 1.55,
         "VIIRS", "Visible Infrared Imaging Radiometer Suite",
         ORANGE)

add_card(slide, 9.0, 2.0, 3.5, 1.55,
         "FIRMS", "Fire Information for Resource Management System",
         GREEN)

add_text(slide, "ANALYSIS CONSIDERATIONS",
         0.9, 4.15, 6, 0.4, 15, CYAN, True)

method_items = [
    "Detection locations",
    "Acquisition dates",
    "Spatial matching",
    "Temporal comparison",
    "Data availability and evidence"
]

for i, item in enumerate(method_items):
    col = i % 2
    row = i // 2
    x = 1.0 + col * 5.5
    y = 4.7 + row * 0.55
    add_bullet(slide, item, x, y, 4.8)

add_footer(slide)


# =====================================================
# SLIDE 6 - SCIENTIFIC RESPONSIBILITY
# =====================================================

slide = new_slide()
add_header(slide, 6, "Scientific Responsibility",
           "Responsible interpretation of satellite hotspot information.")

states = [
    ("DETECTIONS FOUND",
     "Hotspot records were returned for the query.",
     GREEN),
    ("ZERO DETECTIONS",
     "No hotspot records were returned. This does not prove the area was fully observed.",
     YELLOW),
    ("MISSING / INCOMPLETE",
     "The available data is insufficient for a complete interpretation.",
     ORANGE),
    ("UNKNOWN COVERAGE",
     "AOI observation coverage cannot be established from the available evidence.",
     RED)
]

for i, (title, body, accent) in enumerate(states):
    y = 2.0 + i * 0.92
    add_rect(slide, 0.85, y, 11.65, 0.72, PANEL, True)
    add_circle(slide, 1.1, y + 0.22, 0.25, accent)
    add_text(slide, title, 1.6, y + 0.12,
             3.1, 0.35, 13, accent, True)
    add_text(slide, body, 4.6, y + 0.1,
             7.5, 0.5, 11, WHITE)

add_rect(slide, 0.9, 6.0, 11.5, 0.55, PANEL2, True)
add_text(slide,
         "A hotspot is a thermal anomaly — not automatically a confirmed wildfire.",
         1.1, 6.12, 11.1, 0.3, 13, YELLOW, True,
         PP_ALIGN.CENTER)

add_footer(slide)


# =====================================================
# SLIDE 7 - IMPACT AND FUTURE POTENTIAL
# =====================================================

slide = new_slide()
add_header(slide, 7, "Impact and Future Potential",
           "Making satellite fire information easier to explore and interpret.")

add_text(slide, "FIRETRACK AIMS TO SUPPORT",
         0.9, 2.0, 6, 0.4, 15, CYAN, True)

impact = [
    "Geographical exploration",
    "Historical activity analysis",
    "MODIS and VIIRS data exploration",
    "Transparent interpretation of hotspot records"
]

for i, item in enumerate(impact):
    add_bullet(slide, item, 1.0, 2.65 + i * 0.65, 6.0)

# Final project information panel
add_rect(slide, 8.0, 2.0, 4.35, 3.55, PANEL, True)

add_text(slide, "PROJECT INFORMATION",
         8.35, 2.35, 3.6, 0.4, 14, CYAN, True)

add_text(slide, "Project: FIRETRACK",
         8.35, 3.0, 3.5, 0.35, 13, WHITE, True)

add_text(slide, "Challenge: Harmonization of MODIS and VIIRS Hot Spots",
         8.35, 3.55, 3.55, 0.75, 11, MUTED)

add_text(slide,
         "Thank you",
         0.95, 5.8, 6, 0.7, 30, ORANGE, True)

add_footer(slide)


# =====================================================
# SAVE PRESENTATION
# =====================================================

output_file = "FIRETRACK_Demo.pptx"
prs.save(output_file)

print("=" * 55)
print("FIRETRACK PRESENTATION CREATED SUCCESSFULLY!")
print(f"File: {output_file}")
print("Total slides:", len(prs.slides))
print("=" * 55)
