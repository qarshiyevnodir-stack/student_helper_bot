import os
import requests
import json
import logging
import random
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client (Manus pre-configured)
client = OpenAI()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def search_image(query):
    """Search for an image using Unsplash Source API with random seed to avoid duplicates."""
    try:
        # Adding a random seed to get different images for different slides
        seed = random.randint(1, 1000)
        # Fixed: Removed unnecessary backslashes from f-string arguments
        url = f"https://source.unsplash.com/featured/?{query.replace(\' \', \',\')}&sig={seed}"
        response = requests.get(url, allow_redirects=True, timeout=15)
        if response.status_code == 200:
            image_path = f"temp_{hash(query)}_{seed}.jpg"
            # Fixed: Corrected string literal for \'wb\'
            with open(image_path, \'wb\') as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        logging.error(f"Error searching image for \'{query}\': {e}")
    return None

def generate_slide_content(topic, slide_number, total_slides):
    """Generate academic and detailed content for a slide using an LLM."""
    prompt = f"""Siz professional prezentatsiya yaratuvchisiz. Siz o\'zbek tilida yozasiz va akademik, tahliliy yondashuvga egasiz. Mavzu bo\'yicha chuqur ma\'lumot bering.

Mavzu: \'{topic}\'
Jami slaydlar soni: {total_slides}. Bu {slide_number}-slayd.

Ushbu slayd uchun quyidagilarni taqdim eting:
1. \'title\': Qisqa, ammo mazmunli sarlavha.
2. \'content\': 3-4 ta asosiy fikrni o\'z ichiga olgan, akademik uslubdagi, tahliliy ma\'lumotlar. Har bir fikr alohida qatorga yozilsin.
3. \'image_query\': Tegishli rasm uchun 2-3 ta inglizcha kalit so\'zlar.

Javobni FAQAT quyidagi JSON formatida bering:
{{
  \'title\': \'Slayd sarlavhasi\',
  \'content\': [\'Akademik ma\\\'lumot 1\', \'Akademik ma\\\'lumot 2\', \'Akademik ma\\\'lumot 3\'],
  \'image_query\': \'technology computer\'
}}"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": "You are a professional presentation creator. You write in Uzbek language with an academic and analytical approach."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        return data
    except Exception as e:
        logging.error(f"GPT content generation failed for slide {slide_number}: {e}")
        return {"title": f"{topic} - Slayd {slide_number}", "content": ["Ma\'lumot topilmadi. Iltimos, mavzuni aniqlashtiring yoki qayta urinib ko\'ring."], "image_query": topic}

def generate_presentation(topic, slide_count, template_path):
    """Generate a PowerPoint presentation by strictly modifying a template."""
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
        
    prs = Presentation(template_path)
    
    # 1. STICK TO SLIDE COUNT: Remove extra slides or add if needed
    # First, remove extra slides from the end
    while len(prs.slides) > slide_count:
        rId = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[-1]
    
    # If template has fewer slides than requested, add new ones using the second layout (Title and Content)
    while len(prs.slides) < slide_count:
        slide_layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        prs.slides.add_slide(slide_layout)

    # Generate all content first to avoid repeated LLM calls within the loop
    all_slides_content = []
    for i in range(slide_count):
        all_slides_content.append(generate_slide_content(topic, i + 1, slide_count))

    # 2. FILL THE PRESENTATION AND REPLACE IMAGES
    for i, slide_info in enumerate(all_slides_content):
        slide = prs.slides[i]
        
        # Store original font styles from existing text frames before clearing
        original_styles = {}
        for shape in slide.shapes:
            if shape.has_text_frame:
                text_frame = shape.text_frame
                # Check if text_frame is not empty and has paragraphs
                if text_frame.paragraphs:
                    # Iterate through all paragraphs and runs to find a style to preserve
                    for paragraph in text_frame.paragraphs:
                        if paragraph.runs:
                            first_run = paragraph.runs[0]
                            # Store style for the first run of each paragraph
                            original_styles[shape.shape_id] = {
                                \'font_name\': first_run.font.name,
                                \'font_size\': first_run.font.size,
                                \'font_color\': first_run.font.color.rgb if first_run.font.color.rgb else None,
                                \'bold\': first_run.font.bold,
                                \'italic\': first_run.font.italic
                            }
                            break # Only need style from the first paragraph/run

        # Clear all existing text and images
        shapes_to_remove = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                shape.text_frame.clear()
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                shapes_to_remove.append(shape)
        
        for shape in shapes_to_remove:
            sp = shape._element
            sp.getparent().remove(sp)

        # A. Update Title and Content
        if i == 0: # For the first slide, use the full topic in uppercase
            title_text = topic.upper()
            content_points = [] # No content points for the title slide
        else:
            title_text = slide_info.get(\'title\', \'\')
            content_points = slide_info.get(\'content\', [])

        # Find suitable text frames for title and body, or add new ones
        title_shape = None
        body_shape = None

        for shape in slide.shapes:
            if shape.has_text_frame:
                # Prioritize placeholders
                if shape.is_placeholder and \'title\' in shape.name.lower():
                    title_shape = shape
                elif shape.is_placeholder and (\'body\' in shape.name.lower() or \'content\' in shape.name.lower()):
                    body_shape = shape
                # Fallback to any empty text frame if no specific placeholder found
                elif not title_shape and not shape.text_frame.text.strip(): 
                    title_shape = shape
                elif not body_shape and not shape.text_frame.text.strip():
                    body_shape = shape
        
        # If no placeholders or empty text frames, add generic text boxes
        if not title_shape:
            left, top, width, height = Inches(1), Inches(0.5), Inches(8), Inches(1)
            title_shape = slide.shapes.add_textbox(left, top, width, height)
        if not body_shape:
            left, top, width, height = Inches(1), Inches(1.5), Inches(8), Inches(5)
            body_shape = slide.shapes.add_textbox(left, top, width, height)

        # Apply new text and preserve original styles
        if title_shape:
            text_frame = title_shape.text_frame
            text_frame.clear() # Clear again to ensure clean slate
            p = text_frame.paragraphs[0]
            run = p.add_run()
            run.text = title_text
            if title_shape.shape_id in original_styles:
                style = original_styles[title_shape.shape_id]
                if style[\'font_name\']: run.font.name = style[\'font_name\']
                if style[\'font_size\']: run.font.size = style[\'font_size\']
                if style[\'font_color\']: run.font.color.rgb = style[\'font_color\']
                if style[\'bold\'] is not None: run.font.bold = style[\'bold\']
                if style[\'italic\'] is not None: run.font.italic = style[\'italic\']
            
            # Ensure font size is set, default if not found
            if not run.font.size:
                run.font.size = Pt(24) # Default title size

        if body_shape and content_points: # Only add content points if not the title slide and content exists
            text_frame = body_shape.text_frame
            text_frame.clear() # Clear again to ensure clean slate
            for point in content_points:
                p = text_frame.add_paragraph()
                run = p.add_run()
                run.text = point
                if body_shape.shape_id in original_styles:
                    style = original_styles[body_shape.shape_id]
                    if style[\'font_name\']: run.font.name = style[\'font_name\']
                    if style[\'font_size\']: run.font.size = style[\'font_size\']
                    if style[\'font_color\']: run.font.color.rgb = style[\'font_color\']
                    if style[\'bold\'] is not None: run.font.bold = style[\'bold\']
                    if style[\'italic\'] is not None: run.font.italic = style[\'italic\']
                
                # Ensure font size is set, default if not found
                if not run.font.size:
                    run.font.size = Pt(18) # Default body size

        # C. Replace Images
        image_query = slide_info.get(\'image_query\', topic)
        new_image_path = search_image(image_query)
        
        if new_image_path:
            try:
                # Collect all image-like shapes (pictures and picture placeholders)
                image_placeholders = []
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE or \
                       (shape.is_placeholder and shape.placeholder_format.type == 14): # 14 is picture placeholder
                        image_placeholders.append(shape)
                
                if image_placeholders:
                    # Use the first found image shape\'s position and size
                    target_shape = image_placeholders[0]
                    left, top, width, height = target_shape.left, target_shape.top, target_shape.width, target_shape.height
                    
                    # Remove the old picture/placeholder
                    sp = target_shape._element
                    sp.getparent().remove(sp)
                    
                    # Add new picture in the same spot, maintaining aspect ratio if possible
                    slide.shapes.add_picture(new_image_path, left, top, width=width, height=height)
                else:
                    # If no picture or placeholder exists, add it to a default position (right side)
                    slide.shapes.add_picture(new_image_path, Inches(6), Inches(1.5), width=Inches(3.5))
                
                os.remove(new_image_path) # Clean up downloaded image
            except Exception as e:
                logging.error(f"Error replacing image on slide {i}: {e}")
                if os.path.exists(new_image_path):
                    os.remove(new_image_path)
                
    output_filename = f"temp_output_{hash(topic)}.pptx"
    output_path = os.path.join("temp_presentations", output_filename)
    if not os.path.exists("temp_presentations"):
        os.makedirs("temp_presentations")
    prs.save(output_path)
    logging.info(f"Presentation saved to {output_path}")
    return output_path
