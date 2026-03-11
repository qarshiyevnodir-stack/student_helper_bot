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
        formatted_query = query.replace(" ", ",")
        url = f"https://source.unsplash.com/featured/?{formatted_query}&sig={seed}"
        response = requests.get(url, allow_redirects=True, timeout=15)
        if response.status_code == 200:
            image_path = f"temp_{hash(query)}_{seed}.jpg"
            with open(image_path, "wb") as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        logging.error(f"Error searching image for \'{query}\': {e}")
    return None

def generate_slide_content(topic, slide_number, total_slides, language="uz"):
    """Generate academic and detailed content for a slide using an LLM in the specified language."""
    lang_map = {
        "uz": "o\'zbek tilida",
        "en": "English",
        "ru": "русском языке",
        "ko": "한국어로",
        "zh": "中文",
        "de": "Deutsch",
        "kaa": "qoraqalpoq tilida",
        "tk": "turkman tilida",
        "tg": "tojik tilida"
    }
    lang_phrase = lang_map.get(language, "o\'zbek tilida")

    prompt = f"""Siz professional prezentatsiya yaratuvchisiz. Siz {lang_phrase} yozasiz va akademik, tahliliy yondashuvga egasiz. Mavzu bo\'yicha chuqur ma\'lumot bering.\n\nMavzu: \'{topic}\'\nJami slaydlar soni: {total_slides}. Bu {slide_number}-slayd.\n\nUshbu slayd uchun quyidagilarni taqdim eting:\n1. \'title\': Qisqa, ammo mazmunli sarlavha.\n2. \'content\': 3-4 ta asosiy fikrni o\'z ichiga olgan, akademik uslubdagi, tahliliy ma\'lumotlar. Har bir fikr alohida qatorga yozilsin.\n3. \'image_query\': Tegishli rasm uchun 2-3 ta inglizcha kalit so\'zlar.\n\nJavobni FAQAT quyidagi JSON formatida bering:\n{{\n  "title": "Slayd sarlavhasi",\n  "content": ["Akademik ma\'lumot 1", "Akademik ma\'lumot 2", "Akademik ma\'lumot 3"],\n  "image_query": "technology computer"\n}}"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": f"You are a professional presentation creator. You write in {lang_phrase} with an academic and analytical approach."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        logging.info(f"Raw content from GPT for slide {slide_number}: {raw_content}")
        data = json.loads(raw_content)
        logging.info(f"Parsed content for slide {slide_number}: {data}")
        return data
    except Exception as e:
        logging.error(f"GPT content generation failed for slide {slide_number} in {language}: {e}")
        return {"title": f"{topic} - Slayd {slide_number}", "content": ["Ma\"lumot topilmadi."], "image_query": topic}

def find_placeholder_by_type(slide, ph_type):
    for shape in slide.shapes:
        if shape.is_placeholder and shape.placeholder_format.type == ph_type:
            return shape
    return None

def find_placeholder_by_name(slide, ph_name):
    for shape in slide.shapes:
        if shape.is_placeholder and shape.name == ph_name:
            return shape
    return None

def set_text_frame_content_and_style(text_frame, text_lines, ph_config=None, default_font_size=Pt(18), align=PP_ALIGN.LEFT):
    text_frame.clear()
    for i, line in enumerate(text_lines):
        p = text_frame.add_paragraph()
        p.text = line
        p.alignment = align

        run = p.runs[0] if p.runs else p.add_run()

        if ph_config:
            # Apply font styles from config if available
            if ph_config.get("font_name"): run.font.name = ph_config["font_name"]
            if ph_config.get("font_size"): run.font.size = Pt(ph_config["font_size"])
            # Add more style properties as needed (bold, italic, color)
        else:
            # Fallback to default font size if no config or size in config
            if not run.font.size: run.font.size = default_font_size

def generate_presentation(topic, slide_count, template_path, language="uz", name_surname=""):
    """Generate a PowerPoint presentation by strictly modifying a template."""
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
        
    prs = Presentation(template_path)

    # Load template-specific configuration
    template_id = os.path.basename(template_path).split(".")[0]
    config_path = os.path.join(os.path.dirname(template_path), f"template_{template_id}.json")
    template_config = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            template_config = json.load(f)
        logging.info(f"Loaded JSON config for template {template_id}")
    else:
        logging.warning(f"No JSON config found for template {template_id}. Using default logic.")

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
        all_slides_content.append(generate_slide_content(topic, i + 1, slide_count, language))

    # 2. FILL THE PRESENTATION
    for i, slide_info in enumerate(all_slides_content):
        slide = prs.slides[i]
        
        # Get layout index safely
        try:
            layout_idx = prs.slide_layouts.index(slide.slide_layout)
        except ValueError:
            layout_idx = 0  # Default to first layout if not found
        
        logging.info(f"Processing slide {i+1} with layout index: {layout_idx}")
        
        # Clear existing text and pictures
        shapes_to_remove = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                shape.text_frame.clear()
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                shapes_to_remove.append(shape)
        
        for shape in shapes_to_remove:
            sp = shape._element
            sp.getparent().remove(sp)

        # Get slide layout config if available
        current_slide_layout_config = None
        if template_config and "slide_layouts" in template_config:
            for layout_cfg in template_config["slide_layouts"]:
                if layout_cfg["layout_id"] == layout_idx:
                    current_slide_layout_config = layout_cfg
                    logging.info(f"Found config for layout ID {layout_idx}")
                    break

        title_text = ""
        content_points = []
        if i == 0: # Title slide
            title_text = topic.upper()
            if name_surname:
                content_points.append(name_surname.upper())
        else:
            title_text = slide_info.get("title", "")
            content_points = slide_info.get("content", [])

        # Find and fill title placeholder
        title_shape = find_placeholder_by_type(slide, 1) # TITLE placeholder type
        if not title_shape:
            title_shape = find_placeholder_by_name(slide, "Title 1") # Common name
        
        if title_shape:
            logging.info(f"Found title shape: {title_shape.name}")
            # Determine title placeholder config
            title_ph_config = None
            if current_slide_layout_config:
                for ph_cfg in current_slide_layout_config.get("placeholders", []):
                    if ph_cfg.get("ph_idx") == title_shape.placeholder_format.idx:
                        title_ph_config = ph_cfg
                        break

            set_text_frame_content_and_style(title_shape.text_frame, [title_text], 
                               ph_config=title_ph_config,
                               default_font_size=Pt(36), align=PP_ALIGN.CENTER)

        # Find and fill body/content placeholder
        body_shape = find_placeholder_by_type(slide, 2) # BODY placeholder type
        if not body_shape:
            body_shape = find_placeholder_by_name(slide, "Content Placeholder 2") # Common name
        if not body_shape:
            body_shape = find_placeholder_by_name(slide, "Text Placeholder 2") # Another common name

        if body_shape and content_points:
            logging.info(f"Found body shape: {body_shape.name}")
            
            # Determine body placeholder config
            body_ph_config = None
            if current_slide_layout_config:
                for ph_cfg in current_slide_layout_config.get("placeholders", []):
                    if ph_cfg.get("ph_idx") == body_shape.placeholder_format.idx:
                        body_ph_config = ph_cfg
                        break

            set_text_frame_content_and_style(body_shape.text_frame, content_points, 
                                   ph_config=body_ph_config,
                                   default_font_size=Pt(18))

        # Image replacement
        image_query = slide_info.get("image_query", topic)
        new_image_path = search_image(image_query)
        
        if new_image_path:
            try:
                # Try to find an image placeholder from config or by type
                image_placeholder_config = None
                if current_slide_layout_config:
                    for ph_cfg in current_slide_layout_config.get("placeholders", []):
                        if ph_cfg.get("type") == "PICTURE (18)" or (ph_cfg.get("type") == "CONTENT (7)" and "image" in ph_cfg.get("name", "").lower()):
                            image_placeholder_config = ph_cfg
                            break

                if image_placeholder_config:
                    placeholder_name = image_placeholder_config.get("name", "Unknown")
                    logging.info(f"Found image placeholder config: {placeholder_name}")
                    # Convert EMU to Inches (1 inch = 914400 EMU)
                    left = Inches(image_placeholder_config["left"] / 914400)
                    top = Inches(image_placeholder_config["top"] / 914400)
                    width = Inches(image_placeholder_config["width"] / 914400)
                    height = Inches(image_placeholder_config["height"] / 914400)
                    slide.shapes.add_picture(new_image_path, left, top, width=width, height=height)
                else:
                    logging.info("No specific image placeholder config found. Using default position.")
                    # Fallback if no specific image placeholder found
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
