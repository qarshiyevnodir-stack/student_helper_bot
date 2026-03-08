import os
import requests
import json
import logging
import random
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN # Import PP_ALIGN for text alignment
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
        seed = random.randint(1, 1000)
        formatted_query = query.replace(' ', ',')
        url = f"https://source.unsplash.com/featured/?{formatted_query}&sig={seed}"
        response = requests.get(url, allow_redirects=True, timeout=15)
        if response.status_code == 200:
            image_path = f"temp_{hash(query)}_{seed}.jpg"
            with open(image_path, 'wb') as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        logging.error(f"Error searching image for '{query}': {e}")
    return None

def generate_slide_content(topic, slide_number, total_slides):
    """Generate academic and detailed content for a slide using an LLM."""
    prompt = f"""Siz professional prezentatsiya yaratuvchisiz. Siz o'zbek tilida yozasiz va akademik, tahliliy yondashuvga egasiz. Mavzu bo'yicha chuqur ma'lumot bering.

Mavzu: '{topic}'
Jami slaydlar soni: {total_slides}. Bu {slide_number}-slayd.

Ushbu slayd uchun quyidagilarni taqdim eting:
1. 'title': Qisqa, ammo mazmunli sarlavha.
2. 'content': 3-4 ta asosiy fikrni o'z ichiga olgan, akademik uslubdagi, tahliliy ma'lumotlar. Har bir fikr alohida qatorga yozilsin.
3. 'image_query': Tegishli rasm uchun 2-3 ta inglizcha kalit so'zlar.

Javobni FAQAT quyidagi JSON formatida bering:
{{
  "title": "Slayd sarlavhasi",
  "content": ["Akademik ma'lumot 1", "Akademik ma'lumot 2", "Akademik ma'lumot 3"],
  "image_query": "technology computer"
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
        return {"title": f"{topic} - Slayd {slide_number}", "content": ["Ma'lumot topilmadi."], "image_query": topic}

def generate_presentation(topic, slide_count, template_path):
    """Generate a PowerPoint presentation by strictly modifying a template."""
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
        
    prs = Presentation(template_path)
    
    # 1. STICK TO SLIDE COUNT
    while len(prs.slides) > slide_count:
        rId = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[-1]
    
    while len(prs.slides) < slide_count:
        slide_layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        prs.slides.add_slide(slide_layout)

    all_slides_content = []
    for i in range(slide_count):
        all_slides_content.append(generate_slide_content(topic, i + 1, slide_count))

    # 2. FILL THE PRESENTATION
    for i, slide_info in enumerate(all_slides_content):
        slide = prs.slides[i]
        
        original_styles = {}
        for shape in slide.shapes:
            if shape.has_text_frame:
                text_frame = shape.text_frame
                if text_frame.paragraphs:
                    for paragraph in text_frame.paragraphs:
                        if paragraph.runs:
                            first_run = paragraph.runs[0]
                            original_styles[shape.shape_id] = {
                                'font_name': first_run.font.name,
                                'font_size': first_run.font.size,
                                'font_color': first_run.font.color.rgb if first_run.font.color.rgb else None,
                                'bold': first_run.font.bold,
                                'italic': first_run.font.italic
                            }
                            break

        shapes_to_remove = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                shape.text_frame.clear()
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                shapes_to_remove.append(shape)
        
        for shape in shapes_to_remove:
            sp = shape._element
            sp.getparent().remove(sp)

        if i == 0:
            title_text = topic.upper()
            content_points = []
        else:
            title_text = slide_info.get('title', '')
            content_points = slide_info.get('content', [])

        title_shape = None
        body_shape = None

        for shape in slide.shapes:
            if shape.has_text_frame:
                if shape.is_placeholder and 'title' in shape.name.lower():
                    title_shape = shape
                elif shape.is_placeholder and ('body' in shape.name.lower() or 'content' in shape.name.lower()):
                    body_shape = shape
                elif not title_shape and not shape.text_frame.text.strip(): 
                    title_shape = shape
                elif not body_shape and not shape.text_frame.text.strip():
                    body_shape = shape
        
        if not title_shape:
            title_shape = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(8), Inches(1))
        if not body_shape:
            body_shape = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(8), Inches(5))

        if title_shape:
            text_frame = title_shape.text_frame
            text_frame.clear()
            p = text_frame.paragraphs[0]
            run = p.add_run()
            run.text = title_text
            # Center the title text
            p.alignment = PP_ALIGN.CENTER
            if title_shape.shape_id in original_styles:
                style = original_styles[title_shape.shape_id]
                if style['font_name']: run.font.name = style['font_name']
                if style['font_size']: run.font.size = style['font_size']
                if style['font_color']: run.font.color.rgb = style['font_color']
                run.font.bold = style['bold']
                run.font.italic = style['italic']
            if not run.font.size: run.font.size = Pt(24) # Reduced default title font size

        if body_shape and content_points:
            text_frame = body_shape.text_frame
            text_frame.clear()
            for point in content_points:
                p = text_frame.add_paragraph()
                run = p.add_run()
                run.text = point
                if body_shape.shape_id in original_styles:
                    style = original_styles[body_shape.shape_id]
                    if style['font_name']: run.font.name = style['font_name']
                    if style['font_size']: run.font.size = style['font_size']
                    if style['font_color']: run.font.color.rgb = style['font_color']
                    run.font.bold = style['bold']
                    run.font.italic = style['italic']
                if not run.font.size: run.font.size = Pt(14) # Reduced default body font size

        image_query = slide_info.get('image_query', topic)
        new_image_path = search_image(image_query)
        
        if new_image_path:
            try:
                image_placeholders = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE or (s.is_placeholder and s.placeholder_format.type == 14)]
                if image_placeholders:
                    target_shape = image_placeholders[0]
                    left, top, width, height = target_shape.left, target_shape.top, target_shape.width, target_shape.height
                    sp = target_shape._element
                    sp.getparent().remove(sp)
                    slide.shapes.add_picture(new_image_path, left, top, width=width, height=height)
                else:
                    slide.shapes.add_picture(new_image_path, Inches(5.5), Inches(2), width=Inches(4))
                os.remove(new_image_path)
            except Exception as e:
                logging.error(f"Error replacing image: {e}")
                if os.path.exists(new_image_path): os.remove(new_image_path)
                
    output_filename = f"temp_output_{hash(topic)}.pptx"
    output_path = os.path.join("temp_presentations", output_filename)
    if not os.path.exists("temp_presentations"): os.makedirs("temp_presentations")
    prs.save(output_path)
    return output_path
