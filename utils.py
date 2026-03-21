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

def generate_slide_content(topic, slide_number, total_slides, language="uz", is_plan=False, is_conclusion=False):
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

    if is_plan:
       prompt = f"""Siz professional prezentatsiya rejalashtiruvchisisiz. \'{topic}\' mavzusida {total_slides} slayddan iborat prezentatsiya uchun batafsil reja tuzing. Reja sarlavha va 3-4 ta asosiy banddan iborat bo\'lsin. Har bir band qisqa va aniq bo\'lsin. Javobni FAQAT quyidagi JSON formatida bering:\n{{\n  "title": "Reja",\n  "content": ["1. Kirish", "2. Asosiy qism...", "3. Xulosa"]\n}}"""
    elif is_conclusion:
        prompt = f"""Siz professional prezentatsiya yakunlovchisisiz. \'{topic}\' mavzusidagi prezentatsiya uchun yakuniy xulosa yozing. Xulosa 2-3 ta asosiy fikrni o\'z ichiga olsin. Javobni FAQAT quyidagi JSON formatida bering:\n{{\n  "title": "Xulosa",\n  "content": ["Asosiy xulosa 1", "Asosiy xulosa 2"]
}}"""
    else:
        prompt = f"""Siz professional prezentatsiya yaratuvchisiz. Siz {lang_phrase} yozasiz va akademik, tahliliy yondashuvga egasiz. Mavzu bo\'yicha chuqur ma\'lumot bering.\n\nMavzu: '{topic}'\nJami slaydlar soni: {total_slides}. Bu {slide_number}-slayd.\n\nUshbu slayd uchun quyidagilarni taqdim eting:\n1. 'title': Qisqa, ammo mazmunli sarlavha.\n2. 'content': 3-4 ta asosiy fikrni o'z ichiga olgan, akademik uslubdagi, tahliliy ma'lumotlar. Har bir fikr alohida qatorga yozilsin.\n3. 'image_query': Tegishli rasm uchun 2-3 ta inglizcha kalit so'zlar.\n\nJavobni FAQAT quyidagi JSON formatida bering:\n{{\n  "title": "Slayd sarlavhasi",\n  "content": ["Akademik ma'lumot 1", "Akademik ma'lumot 2", "Akademik ma'lumot 3"],\n  "image_query": "technology computer"\n}}"""
    
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
        return {"title": f"{topic} - Slayd {slide_number}", "content": ["Ma'lumot topilmadi."], "image_query": topic}

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

def find_best_shape_for_text(slide, type_hint="title"):
    """Find the best shape to put text into, even if it's not a standard placeholder."""
    # 1. Try standard placeholders first
    if type_hint == "title":
        ph = find_placeholder_by_type(slide, 1) # TITLE
        if ph: return ph
    else:
        ph = find_placeholder_by_type(slide, 2) # BODY
        if ph: return ph

    # 2. Try shapes by name
    if type_hint == "title":
        for name in ["Title", "Sarlavha", "Heading", "TextBox 12", "TextBox 15"]:
            for shape in slide.shapes:
                if name.lower() in shape.name.lower() and hasattr(shape, "text_frame"):
                    return shape
    else:
        for name in ["Content", "Body", "Matn", "TextBox 13", "TextBox 16", "TextBox 10", "TextBox 9"]:
            for shape in slide.shapes:
                if name.lower() in shape.name.lower() and hasattr(shape, "text_frame"):
                    return shape

    # 3. Fallback: Find any shape with a text frame that isn't empty or has a specific index
    shapes_with_text = [s for s in slide.shapes if hasattr(s, "text_frame")]
    if type_hint == "title" and shapes_with_text:
        return shapes_with_text[0]
    elif len(shapes_with_text) > 1:
        return shapes_with_text[1]
    elif shapes_with_text:
        return shapes_with_text[0]

    return None

def set_text_frame_content_and_style(text_frame, text_lines, ph_config=None, default_font_size=Pt(16), align=PP_ALIGN.LEFT):
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

def generate_template_1_presentation(prs, topic, slide_count, language="uz", name_surname="", plan=None):
    # Define specific shape IDs and placeholder types for this template
    # Based on the analysis from analyze_template.py
    template_layouts = {
        # Slide 1: Title Slide
        0: {
            "title": {"ph_type": 3, "ph_idx": 0}, # CENTER_TITLE
            "subtitle": {"ph_type": 4, "ph_idx": 1} # SUBTITLE
        },
        # Slide 2: Plan Slide
        1: {
            "title": {"ph_type": 1, "ph_idx": 0}, # TITLE
            "body": {"ph_type": 2, "ph_idx": 1} # BODY
        },
        # Slide 3: Content Slide 1 (BLANK_1_1_1_1_1_1)
        2: {
            "title": {"ph_type": 1, "ph_idx": 0}, # TITLE
            "subtitle": {"ph_type": 4, "ph_idx": 1}, # SUBTITLE
            "body1": {"shape_id": 34, "shape_type": MSO_SHAPE_TYPE.TEXT_BOX},
            "body2": {"shape_id": 37, "shape_type": MSO_SHAPE_TYPE.TEXT_BOX}
        },
        # Slide 4: Content Slide 2 (TITLE_AND_TWO_COLUMNS_1_1)
        3: {
            "title": {"ph_type": 1, "ph_idx": 0}, # TITLE
            "subtitle1": {"ph_type": 4, "ph_idx": 1}, # SUBTITLE
            "subtitle2": {"ph_type": 4, "ph_idx": 2} # SUBTITLE
        },
        # Slide 5: Content Slide 3 (ONE_COLUMN_TEXT with image)
        4: {
            "title": {"ph_type": 1, "ph_idx": 0}, # TITLE
            "subtitle": {"ph_type": 4, "ph_idx": 1}, # SUBTITLE
            "image": {"ph_type": 18, "ph_idx": 2} # PICTURE
        },
        # Slide 6: Content Slide 4 (BLANK_1_1)
        5: {
            "title": {"ph_type": 1, "ph_idx": 0}, # TITLE
            "subtitle": {"ph_type": 4, "ph_idx": 1} # SUBTITLE
        },
        # Slide 7: Content Slide 5 (CUSTOM with image)
        6: {
            "title": {"ph_type": 1, "ph_idx": 0}, # TITLE
            "subtitle": {"ph_type": 4, "ph_idx": 1}, # SUBTITLE
            "image": {"ph_type": 18, "ph_idx": 2} # PICTURE
        },
        # Slide 8: Conclusion Slide
        7: {
            "title": {"ph_type": 1, "ph_idx": 0}, # TITLE
            "body": {"ph_type": 2, "ph_idx": 1} # BODY
        }
    }

    # Ensure we have enough slides in the presentation object
    # The template has 8 slides, so we need to add/remove content slides (3-7)
    # based on the requested slide_count.
    # Total slides = 1 (Title) + 1 (Plan) + slide_count (Content) + 1 (Conclusion)
    required_total_slides = 1 + 1 + slide_count + 1

    # Remove extra slides if any (assuming template has more than 8 or we need fewer content slides)
    while len(prs.slides) > required_total_slides:
        rId = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[-1]

    # Add missing slides if needed
    while len(prs.slides) < required_total_slides:
        # Use a content slide layout for new slides (e.g., layout of slide 3 or 5)
        # For simplicity, let's use the layout of slide 3 (index 2 in template_layouts)
        # This needs to be dynamic based on the template's actual layouts
        # For now, we'll just add a blank slide and fill it later
        slide_layout = prs.slide_layouts[2] # Assuming layout index 2 is a good content slide layout
        prs.slides.add_slide(slide_layout)

    all_slides_content = []
    # Generate title slide content
    all_slides_content.append({"title": topic, "content": [name_surname] if name_surname else []})

    # Generate plan slide content
    if plan is None:
        plan = generate_slide_content(topic, 2, required_total_slides, language, is_plan=True)
    all_slides_content.append(plan)

    # Generate main content slides
    content_slide_layouts = [2, 3, 4, 5, 6] # Indices for content slides in template_layouts
    for i in range(slide_count):
        # Cycle through content slide layouts
        content_layout_idx = content_slide_layouts[i % len(content_slide_layouts)]
        all_slides_content.append(generate_slide_content(topic, i + 1 + 2, required_total_slides, language))

    # Generate conclusion slide content
    conclusion_content = generate_slide_content(topic, required_total_slides, required_total_slides, language, is_conclusion=True)
    all_slides_content.append(conclusion_content)

    # Fill the presentation
    for i, slide_info in enumerate(all_slides_content):
        slide = prs.slides[i]
        current_slide_layout_config = template_layouts.get(i) # Get specific layout config for this slide index

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

        title_text = slide_info.get("title", "")
        content_points = slide_info.get("content", [])
        image_query = slide_info.get("image_query", topic) if i > 0 and i < required_total_slides - 1 else None

        # Apply content based on slide type and template layout
        if i == 0: # Title slide
            title_shape_config = current_slide_layout_config.get("title")
            subtitle_shape_config = current_slide_layout_config.get("subtitle")
            if title_shape_config:
                title_shape = find_placeholder_by_type(slide, title_shape_config["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [topic.upper()])
            if subtitle_shape_config and name_surname:
                subtitle_shape = find_placeholder_by_type(slide, subtitle_shape_config["ph_type"])
                if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, [name_surname.upper()])

        elif i == 1: # Plan slide
            title_shape_config = current_slide_layout_config.get("title")
            body_shape_config = current_slide_layout_config.get("body")
            if title_shape_config:
                title_shape = find_placeholder_by_type(slide, title_shape_config["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [plan.get("title", "Reja")])
            if body_shape_config:
                body_shape = find_placeholder_by_type(slide, body_shape_config["ph_type"])
                if body_shape: set_text_frame_content_and_style(body_shape.text_frame, plan.get("content", []))

        elif i == required_total_slides - 1: # Conclusion slide
            title_shape_config = current_slide_layout_config.get("title")
            body_shape_config = current_slide_layout_config.get("body")
            if title_shape_config:
                title_shape = find_placeholder_by_type(slide, title_shape_config["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [conclusion_content.get("title", "Xulosa")])
            if body_shape_config:
                body_shape = find_placeholder_by_type(slide, body_shape_config["ph_type"])
                if body_shape: set_text_frame_content_and_style(body_shape.text_frame, conclusion_content.get("content", []))

        else: # Content slides (dynamic based on content_layout_idx)
            # Handle content slides based on their specific layout configs
            if current_slide_layout_config:
                # Fill title
                title_shape_config = current_slide_layout_config.get("title")
                if title_shape_config:
                    title_shape = find_placeholder_by_type(slide, title_shape_config["ph_type"])
                    if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [title_text])

                # Determine which content slide layout is being used
                content_slide_index_in_cycle = (i - 2) % len(content_slide_layouts) # Adjust index for 0-based content slides

                if content_slide_index_in_cycle == 0: # Slide 3 layout (index 2 in template_layouts)
                    subtitle_shape_config = current_slide_layout_config.get("subtitle")
                    if subtitle_shape_config:
                        subtitle_shape = find_placeholder_by_type(slide, subtitle_shape_config["ph_type"])
                        if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, [content_points[0]] if content_points else [])
                    
                    # Find text boxes by shape_id
                    body1_shape = next((s for s in slide.shapes if s.shape_id == 34 and s.shape_type == MSO_SHAPE_TYPE.TEXT_BOX), None)
                    if body1_shape: set_text_frame_content_and_style(body1_shape.text_frame, [content_points[1]] if len(content_points) > 1 else [])

                    body2_shape = next((s for s in slide.shapes if s.shape_id == 37 and s.shape_type == MSO_SHAPE_TYPE.TEXT_BOX), None)
                    if body2_shape: set_text_frame_content_and_style(body2_shape.text_frame, [content_points[2]] if len(content_points) > 2 else [])

                elif content_slide_index_in_cycle == 1: # Slide 4 layout (index 3 in template_layouts)
                    subtitle1_shape_config = current_slide_layout_config.get("subtitle1")
                    if subtitle1_shape_config:
                        subtitle1_shape = find_placeholder_by_type(slide, subtitle1_shape_config["ph_type"])
                        if subtitle1_shape: set_text_frame_content_and_style(subtitle1_shape.text_frame, [content_points[0]] if content_points else [])
                    
                    subtitle2_shape_config = current_slide_layout_config.get("subtitle2")
                    if subtitle2_shape_config:
                        subtitle2_shape = find_placeholder_by_type(slide, subtitle2_shape_config["ph_type"])
                        if subtitle2_shape: set_text_frame_content_and_style(subtitle2_shape.text_frame, [content_points[1]] if len(content_points) > 1 else [])

                elif content_slide_index_in_cycle == 2: # Slide 5 layout (index 4 in template_layouts)
                    subtitle_shape_config = current_slide_layout_config.get("subtitle")
                    if subtitle_shape_config:
                        subtitle_shape = find_placeholder_by_type(slide, subtitle_shape_config["ph_type"])
                        if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, [content_points[0]] if content_points else [])
                    
                    image_shape_config = current_slide_layout_config.get("image")
                    if image_shape_config and image_query:
                        image_placeholder = find_placeholder_by_type(slide, image_shape_config["ph_type"])
                        if image_placeholder:
                            image_path = search_image(image_query)
                            if image_path:
                                try:
                                    left = image_placeholder.left
                                    top = image_placeholder.top
                                    width = image_placeholder.width
                                    height = image_placeholder.height
                                    slide.shapes.add_picture(image_path, left, top, width, height)
                                    os.remove(image_path)
                                except Exception as e:
                                    logging.error(f"Error adding image to slide {i+1}: {e}")

                elif content_slide_index_in_cycle == 3: # Slide 6 layout (index 5 in template_layouts)
                    subtitle_shape_config = current_slide_layout_config.get("subtitle")
                    if subtitle_shape_config:
                        subtitle_shape = find_placeholder_by_type(slide, subtitle_shape_config["ph_type"])
                        if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, [content_points[0]] if content_points else [])

                elif content_slide_index_in_cycle == 4: # Slide 7 layout (index 6 in template_layouts)
                    subtitle_shape_config = current_slide_layout_config.get("subtitle")
                    if subtitle_shape_config:
                        subtitle_shape = find_placeholder_by_type(slide, subtitle_shape_config["ph_type"])
                        if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, [content_points[0]] if content_points else [])
                    
                    image_shape_config = current_slide_layout_config.get("image")
                    if image_shape_config and image_query:
                        image_placeholder = find_placeholder_by_type(slide, image_shape_config["ph_type"])
                        if image_placeholder:
                            image_path = search_image(image_query)
                            if image_path:
                                try:
                                    left = image_placeholder.left
                                    top = image_placeholder.top
                                    width = image_placeholder.width
                                    height = image_placeholder.height
                                    slide.shapes.add_picture(image_path, left, top, width, height)
                                    os.remove(image_path)
                                except Exception as e:
                                    logging.error(f"Error adding image to slide {i+1}: {e}")

    # Save the presentation
    output_path = f"generated_presentation_{hash(topic)}.pptx"
    prs.save(output_path)
    return output_path

def generate_presentation(topic, slide_count, template_path, language="uz", name_surname="", plan=None):
    """Generate a PowerPoint presentation by strictly modifying a template."""
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
        
    prs = Presentation(template_path)

    # Check if it's template 1 and use the specific function
    template_id = os.path.basename(template_path).split(".")[0]
    if template_id == "1":
        return generate_template_1_presentation(prs, topic, slide_count, language, name_surname, plan)

    # Fallback to generic generation if not template 1
    # Load template-specific configuration
    config_path = os.path.join(os.path.dirname(template_path), f"template_{template_id}.json")
    template_config = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            template_config = json.load(f)
        logging.info(f"Loaded JSON config for template {template_id}")
    else:
        logging.warning(f"No JSON config found for template {template_id}. Using default logic.")

    # Calculate actual total slides needed
    actual_total_slides = slide_count + 2  # Title + Content Slides + Conclusion
    if plan: # Add 1 for outline slide if plan is provided
        actual_total_slides += 1

    # 1. STICK TO SLIDE COUNT
    while len(prs.slides) > actual_total_slides:
        rId = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[-1]
    
    while len(prs.slides) < actual_total_slides:
        slide_layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        prs.slides.add_slide(slide_layout)

    all_slides_content = []
    # Generate title slide content (placeholder)
    all_slides_content.append({"title": topic, "content": [name_surname] if name_surname else []})

    # Generate plan slide content
    if plan:
        all_slides_content.append(plan)

    # Generate main content slides
    # The slide_number for content slides should be relative to the overall presentation
    # The total_slides for content generation should be the actual_total_slides
    for i in range(slide_count):
        all_slides_content.append(generate_slide_content(topic, i + 1 + (2 if plan else 1), actual_total_slides, language))

    # Generate conclusion slide content
    # The slide_number for the conclusion slide should be the last slide in the overall presentation
    # The total_slides for the conclusion prompt should be the actual_total_slides
    conclusion_content = generate_slide_content(topic, actual_total_slides, actual_total_slides, language, is_conclusion=True)
    all_slides_content.append(conclusion_content)

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

        title_text = slide_info.get("title", "")
        content_points = slide_info.get("content", [])

        if i == 0: # Title slide
            title_text = topic.upper()
            if name_surname:
                content_points = [name_surname.upper()]
        elif plan and i == 1: # Plan slide (if plan exists)
            title_text = plan.get("title", "Reja")
            content_points = plan.get("content", [])
        elif i == actual_total_slides - 1: # Conclusion slide
            title_text = slide_info.get("title", "Xulosa")
            content_points = slide_info.get("content", [])
        # For other slides, title_text and content_points are already set from slide_info

        # Find and fill title placeholder
        title_shape = find_best_shape_for_text(slide, "title")
        
        if title_shape:
            logging.info(f"Found title shape: {title_shape.name}")
            # Determine title placeholder config
            title_ph_config = None
            if current_slide_layout_config and hasattr(title_shape, 'placeholder_format'):
                try:
                    title_ph_config = next((ph for ph in current_slide_layout_config["placeholders"] if ph["ph_idx"] == title_shape.placeholder_format.idx), None)
                except KeyError:
                    pass
            set_text_frame_content_and_style(title_shape.text_frame, [title_text], title_ph_config, default_font_size=Pt(24))

        # Find and fill body placeholder
        body_shape = find_best_shape_for_text(slide, "body")
        if body_shape:
            logging.info(f"Found body shape: {body_shape.name}")
            # Determine body placeholder config
            body_ph_config = None
            if current_slide_layout_config and hasattr(body_shape, 'placeholder_format'):
                try:
                    body_ph_config = next((ph for ph in current_slide_layout_config["placeholders"] if ph["ph_idx"] == body_shape.placeholder_format.idx), None)
                except KeyError:
                    pass
            set_text_frame_content_and_style(body_shape.text_frame, content_points, body_ph_config, default_font_size=Pt(18))

        # Image insertion for content slides (not title or conclusion)
        if i > 0 and i < actual_total_slides - 1:
            image_query = slide_info.get("image_query", topic)
            if image_query:
                image_path = search_image(image_query)
                if image_path:
                    try:
                        # Find an image placeholder or a suitable shape for image
                        img_placeholder = find_placeholder_by_type(slide, 18) # PICTURE placeholder type
                        if img_placeholder:
                            left = img_placeholder.left
                            top = img_placeholder.top
                            width = img_placeholder.width
                            height = img_placeholder.height
                            slide.shapes.add_picture(image_path, left, top, width, height)
                        else:
                            # Fallback to adding image at a default position if no placeholder
                            slide.shapes.add_picture(image_path, Inches(1), Inches(2), Inches(4), Inches(3))
                        os.remove(image_path) # Clean up temp image
                    except Exception as e:
                        logging.error(f"Error adding image to slide {i+1}: {e}")

    # Save the presentation
    output_path = f"generated_presentation_{hash(topic)}.pptx"
    prs.save(output_path)
    return output_path
    return output_path

def generate_presentation(topic, slide_count, template_path, language="uz", name_surname="", plan=None):
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

    # Calculate actual total slides needed
    actual_total_slides = slide_count + 2  # Title + Content Slides + Conclusion
    if plan: # Add 1 for outline slide if plan is provided
        actual_total_slides += 1

    # 1. STICK TO SLIDE COUNT
    while len(prs.slides) > actual_total_slides:
        rId = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[-1]
    
    while len(prs.slides) < actual_total_slides:
        slide_layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        prs.slides.add_slide(slide_layout)

    all_slides_content = []
    # Generate title slide content (placeholder)
    all_slides_content.append({"title": topic, "content": [name_surname] if name_surname else []})

    # Generate plan slide content
    if plan:
        all_slides_content.append(plan)

    # Generate main content slides
    # The slide_number for content slides should be relative to the overall presentation
    # The total_slides for content generation should be the actual_total_slides
    for i in range(slide_count):
        all_slides_content.append(generate_slide_content(topic, i + 1 + (2 if plan else 1), actual_total_slides, language))

    # Generate conclusion slide content
    # The slide_number for the conclusion slide should be the last slide in the overall presentation
    # The total_slides for the conclusion prompt should be the actual_total_slides
    conclusion_content = generate_slide_content(topic, actual_total_slides, actual_total_slides, language, is_conclusion=True)
    all_slides_content.append(conclusion_content)

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

        title_text = slide_info.get("title", "")
        content_points = slide_info.get("content", [])

        if i == 0: # Title slide
            title_text = topic.upper()
            if name_surname:
                content_points = [name_surname.upper()]
        elif plan and i == 1: # Plan slide (if plan exists)
            title_text = plan.get("title", "Reja")
            content_points = plan.get("content", [])
        elif i == actual_total_slides - 1: # Conclusion slide
            title_text = slide_info.get("title", "Xulosa")
            content_points = slide_info.get("content", [])
        # For other slides, title_text and content_points are already set from slide_info

        # Find and fill title placeholder
        title_shape = find_best_shape_for_text(slide, "title")
        
        if title_shape:
            logging.info(f"Found title shape: {title_shape.name}")
            # Determine title placeholder config
            title_ph_config = None
            if current_slide_layout_config and hasattr(title_shape, 'placeholder_format'):
                try:
                    ph_idx = title_shape.placeholder_format.idx
                    for ph_cfg in current_slide_layout_config.get("placeholders", []):
                        if ph_cfg.get("ph_idx") == ph_idx:
                            title_ph_config = ph_cfg
                            break
                except AttributeError:
                    logging.warning(f"Shape {title_shape.name} does not have placeholder_format.idx")

            # Apply specific formatting for the title slide
            if i == 0:
                set_text_frame_content_and_style(title_shape.text_frame, [title_text], 
                                   ph_config=title_ph_config,
                                   default_font_size=Pt(40), align=PP_ALIGN.CENTER)
            elif plan and i == 1: # Outline slide
                set_text_frame_content_and_style(title_shape.text_frame, [title_text], 
                                   ph_config=title_ph_config,
                                   default_font_size=Pt(30), align=PP_ALIGN.CENTER)
            elif i == actual_total_slides - 1: # Conclusion slide
                set_text_frame_content_and_style(title_shape.text_frame, [title_text], 
                                   ph_config=title_ph_config,
                                   default_font_size=Pt(30), align=PP_ALIGN.CENTER)
            else:
                set_text_frame_content_and_style(title_shape.text_frame, [title_text], 
                                   ph_config=title_ph_config,
                                   default_font_size=Pt(30), align=PP_ALIGN.LEFT)

        # Find and fill body/content placeholder
        body_shape = find_best_shape_for_text(slide, "body")

        if body_shape and content_points:
            logging.info(f"Found body shape: {body_shape.name}")
            
            # Determine body placeholder config
            body_ph_config = None
            if current_slide_layout_config and hasattr(body_shape, 'placeholder_format'):
                try:
                    ph_idx = body_shape.placeholder_format.idx
                    for ph_cfg in current_slide_layout_config.get("placeholders", []):
                        if ph_cfg.get("ph_idx") == ph_idx:
                            body_ph_config = ph_cfg
                            break
                except AttributeError:
                    logging.warning(f"Shape {body_shape.name} does not have placeholder_format.idx")

            # Apply specific formatting for the author on the title slide
            if i == 0 and name_surname:
                set_text_frame_content_and_style(body_shape.text_frame, content_points, 
                                       ph_config=body_ph_config,
                                       default_font_size=Pt(20), align=PP_ALIGN.CENTER)
            elif plan and i == 1: # Outline slide content
                set_text_frame_content_and_style(body_shape.text_frame, content_points, 
                                       ph_config=body_ph_config,
                                       default_font_size=Pt(16), align=PP_ALIGN.LEFT)
            elif i == actual_total_slides - 1: # Conclusion slide content
                set_text_frame_content_and_style(body_shape.text_frame, content_points, 
                                       ph_config=body_ph_config,
                                       default_font_size=Pt(16), align=PP_ALIGN.LEFT)
            else:
                set_text_frame_content_and_style(body_shape.text_frame, content_points, 
                                       ph_config=body_ph_config,
                                       default_font_size=Pt(16), align=PP_ALIGN.LEFT)

        # Image replacement - Add images to content slides (not title or conclusion)
        if i > 0 and i < actual_total_slides - 1:  # Skip title and conclusion slides
            image_query = slide_info.get("image_query", topic)
            new_image_path = search_image(image_query)
        
            if new_image_path:
                try:
                    image_placeholder_config = None
                    if current_slide_layout_config:
                        for ph_cfg in current_slide_layout_config.get("placeholders", []):
                            if ph_cfg.get("type") == "PICTURE (18)" or (ph_cfg.get("type") == "CONTENT (7)" and "image" in ph_cfg.get("name", "").lower()):
                                image_placeholder_config = ph_cfg
                                break

                    if image_placeholder_config:
                        placeholder_name = image_placeholder_config.get("name", "Unknown")
                        logging.info(f"Found image placeholder config: {placeholder_name}")
                        left = Inches(image_placeholder_config["left"] / 914400)
                        top = Inches(image_placeholder_config["top"] / 914400)
                        width = Inches(image_placeholder_config["width"] / 914400)
                        height = Inches(image_placeholder_config["height"] / 914400)
                        slide.shapes.add_picture(new_image_path, left, top, width=width, height=height)
                    else:
                        logging.info("No specific image placeholder config found. Using default position.")
                        slide.shapes.add_picture(new_image_path, Inches(5.5), Inches(2), width=Inches(4), height=Inches(3))
                    logging.info(f"Successfully added image to slide {i+1}")
                    os.remove(new_image_path)
                except Exception as e:
                    logging.error(f"Error adding image to slide {i+1}: {e}")
                    if os.path.exists(new_image_path): os.remove(new_image_path)
                
    output_filename = f"temp_output_{hash(topic)}.pptx"
    output_path = os.path.join("temp_presentations", output_filename)
    if not os.path.exists("temp_presentations"): os.makedirs("temp_presentations")
    prs.save(output_path)
    return output_path
