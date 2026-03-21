
import logging
import os
import random
import requests
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, MSO_VERTICAL_ALIGNMENT
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = OpenAI()

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

def set_text_frame_content_and_style(text_frame, content_list, font_size=None, is_title=False, is_subtitle=False):
    text_frame.clear()
    tf = text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_VERTICAL_ALIGNMENT.TOP
    tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT

    for i, paragraph_text in enumerate(content_list):
        p = tf.add_paragraph()
        p.text = paragraph_text
        if is_title:
            p.font.size = Pt(44) if font_size is None else Pt(font_size)
            p.font.bold = True
        elif is_subtitle:
            p.font.size = Pt(24) if font_size is None else Pt(font_size)
            p.font.bold = False
        else:
            p.font.size = Pt(18) if font_size is None else Pt(font_size)
            p.font.bold = False
        
        # Adjust font size if text overflows
        # This is a basic check and might need more sophisticated logic
        if len(paragraph_text) > 100 and not is_title and not is_subtitle:
            p.font.size = Pt(14)
        elif len(paragraph_text) > 200 and not is_title and not is_subtitle:
            p.font.size = Pt(12)

def find_placeholder_by_type(slide, ph_type):
    for shape in slide.placeholders:
        if shape.placeholder_format.type == ph_type:
            return shape
    return None

def add_image_to_slide(slide, image_query, left, top, width, height):
    if not UNSPLASH_ACCESS_KEY:
        logging.warning("UNSPLASH_ACCESS_KEY is not set. Image search will be skipped.")
        return

    try:
        search_url = f"https://api.unsplash.com/search/photos?query={image_query}&per_page=1&client_id={UNSPLASH_ACCESS_KEY}"
        response = requests.get(search_url)
        response.raise_for_status()
        data = response.json()
        if data['results']:
            image_url = data['results'][0]['urls']['regular']
            image_data = requests.get(image_url).content
            image_path = f"temp_image_{random.randint(0, 10000)}.jpg"
            with open(image_path, "wb") as f:
                f.write(image_data)
            slide.shapes.add_picture(image_path, left, top, width, height)
            os.remove(image_path)
            logging.info(f"Image '{image_query}' added to slide.")
        else:
            logging.warning(f"No image found for query: {image_query}")
    except Exception as e:
        logging.error(f"Error adding image '{image_query}': {e}")

def generate_slide_content(topic, slide_number, total_slides, language, is_plan=False, is_conclusion=False):
    prompt = f"Generate content for a presentation slide. The topic is '{topic}'. This is slide {slide_number} of {total_slides}. Language: {language}."
    if is_plan:
        prompt = f"Generate a concise outline/plan for a presentation on '{topic}'. Provide 3-4 main points. Language: {language}."
    elif is_conclusion:
        prompt = f"Generate a concise conclusion for a presentation on '{topic}'. Summarize key takeaways. Language: {language}."
    else:
        prompt += " Provide a title and 3-4 bullet points of content. Also suggest a relevant image search query."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates presentation slide content in JSON format. Ensure all text is in the specified language. For content slides, provide 'title', 'content' (list of bullet points), and 'image_query'. For plan/conclusion, provide 'title' and 'content' (list of bullet points)."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        logging.info(f"Raw content from GPT for slide {slide_number}: {content}")
        parsed_content = json.loads(content)
        logging.info(f"Parsed content for slide {slide_number}: {parsed_content}")
        return parsed_content
    except Exception as e:
        logging.error(f"Error generating content for slide {slide_number}: {e}")
        return None

def generate_presentation(prs, topic, slide_count, language, name_surname=""):
    # This is the old, general function. We will use this as a fallback for now.
    # It will be replaced by template-specific functions later.
    
    # Generate content for all slides
    all_slides_content = []

    # Title slide
    all_slides_content.append({"title": topic, "content": [name_surname] if name_surname else []})

    # Plan slide
    plan = generate_slide_content(topic, 2, slide_count + 2, language, is_plan=True)
    if plan is None:
        plan = {"title": "Reja", "content": ["Kirish", "Asosiy qism", "Xulosa"]}
    all_slides_content.append(plan)

    # Main content slides
    for i in range(slide_count):
        all_slides_content.append(generate_slide_content(topic, i + 1 + 2, slide_count + 2, language))

    # Conclusion slide
    conclusion_content = generate_slide_content(topic, slide_count + 2, slide_count + 2, language, is_conclusion=True)
    if conclusion_content is None:
        conclusion_content = {"title": "Xulosa", "content": ["Asosiy xulosa"]}
    all_slides_content.append(conclusion_content)

    # Fill the presentation
    for i, slide_info in enumerate(all_slides_content):
        if slide_info is None:
            slide_info = {"title": f"Slayd {i}", "content": []}

        slide = prs.slides[i]

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
        image_query = slide_info.get("image_query", topic) if i > 0 and i < slide_count + 1 else None

        # Apply content based on slide type
        if i == 0: # Title slide
            title_shape = find_placeholder_by_type(slide, 3) # CENTER_TITLE
            subtitle_shape = find_placeholder_by_type(slide, 4) # SUBTITLE
            if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [topic.upper()], is_title=True)
            if subtitle_shape and name_surname: set_text_frame_content_and_style(subtitle_shape.text_frame, [name_surname.upper()], is_subtitle=True)
        elif i == 1: # Plan slide
            title_shape = find_placeholder_by_type(slide, 1) # TITLE
            body_shape = find_placeholder_by_type(slide, 2) # BODY
            if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [plan.get("title", "Reja")], is_title=True)
            if body_shape: set_text_frame_content_and_style(body_shape.text_frame, plan.get("content", []))
        elif i == slide_count + 1: # Conclusion slide
            title_shape = find_placeholder_by_type(slide, 1) # TITLE
            body_shape = find_placeholder_by_type(slide, 2) # BODY
            if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [conclusion_content.get("title", "Xulosa")], is_title=True)
            if body_shape: set_text_frame_content_and_style(body_shape.text_frame, conclusion_content.get("content", []))
        else: # Content slides
            title_shape = find_placeholder_by_type(slide, 1) # TITLE
            body_shape = find_placeholder_by_type(slide, 2) # BODY
            if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [title_text], is_title=True)
            if body_shape: set_text_frame_content_and_style(body_shape.text_frame, content_points)
            if image_query:
                # Attempt to find a picture placeholder or add to a default location
                pic_placeholder = find_placeholder_by_type(slide, 18) # PICTURE
                if pic_placeholder:
                    add_image_to_slide(slide, image_query, pic_placeholder.left, pic_placeholder.top, pic_placeholder.width, pic_placeholder.height)
                else:
                    # Fallback to adding image at a default position if no placeholder is found
                    add_image_to_slide(slide, image_query, Inches(7), Inches(1.5), Inches(2.5), Inches(2.5))

    output_path = f"generated_presentations/{topic}_{random.randint(1000, 9999)}.pptx"
    prs.save(output_path)
    return output_path

def generate_template_1_presentation(prs, topic, requested_slide_count, language, name_surname="", plan=None):
    logging.info(f"Generating presentation for template 1 with topic: {topic}, slides: {requested_slide_count}")

    # Define template specific layout mappings based on analysis
    template_layouts = {
        0: {"layout_name": "TITLE", "title": {"ph_type": 3}, "subtitle": {"ph_type": 4}},
        1: {"layout_name": "TITLE_AND_BODY", "title": {"ph_type": 1}, "body": {"ph_type": 2}},
        2: {"layout_name": "BLANK_1_1_1_1_1_1", "title": {"ph_type": 1}, "subtitle": {"ph_type": 4}, "text_box_1": {"id": 34}, "text_box_2": {"id": 37}},
        3: {"layout_name": "TITLE_AND_TWO_COLUMNS_1_1", "title": {"ph_type": 1}, "subtitle_1": {"ph_type": 4}, "subtitle_2": {"ph_type": 4}},
        4: {"layout_name": "ONE_COLUMN_TEXT", "title": {"ph_type": 1}, "subtitle": {"ph_type": 4}, "picture": {"ph_type": 18}},
        5: {"layout_name": "BLANK_1_1", "title": {"ph_type": 1}, "subtitle": {"ph_type": 4}},
        6: {"layout_name": "CUSTOM", "title": {"ph_type": 1}, "subtitle": {"ph_type": 4}, "picture": {"ph_type": 18}},
        7: {"layout_name": "TITLE_AND_BODY_1", "title": {"ph_type": 1}, "body": {"ph_type": 2}}
    }

    # Ensure required_total_slides is at least 8 (title, plan, 5 content, conclusion)
    required_total_slides = max(requested_slide_count, 5) + 3 # 1 title, 1 plan, 5 content, 1 conclusion

    all_slides_content = []

    # 1. Title slide (index 0)
    title_slide_content = {"title": topic, "content": [name_surname] if name_surname else []}
    all_slides_content.append(title_slide_content)

    # 2. Plan slide (index 1)
    if plan is None:
        plan = generate_slide_content(topic, 2, required_total_slides, language, is_plan=True)
    if plan is None:  # Double check in case generation failed
        plan = {"title": "Reja", "content": ["Kirish", "Asosiy qism", "Xulosa"]}
    all_slides_content.append(plan)

    # 3-7. Main content slides (indices 2 to 6 in the template, dynamically repeated)
    content_slide_layouts_indices = [2, 3, 4, 5, 6] # Corresponds to template_layouts keys
    for i in range(requested_slide_count):
        # Cycle through the 5 content slide layouts
        template_layout_index = content_slide_layouts_indices[i % len(content_slide_layouts_indices)]
        slide_content = generate_slide_content(topic, i + 1 + 2, required_total_slides, language)
        if slide_content is None:
            slide_content = {"title": f"Slayd {i+3}", "content": ["Bu slayd mazmuni hozircha mavjud emas."], "image_query": topic}
        all_slides_content.append(slide_content)

    # 8. Conclusion slide (index 7 in the template)
    conclusion_content = generate_slide_content(topic, required_total_slides, required_total_slides, language, is_conclusion=True)
    if conclusion_content is None:
        conclusion_content = {"title": "Xulosa", "content": ["Asosiy xulosa"]}
    all_slides_content.append(conclusion_content)

    # Ensure we have enough slides in the presentation object
    # If requested_slide_count is more than 5, we need to add more content slides
    current_prs_slides_count = len(prs.slides)
    while len(all_slides_content) > current_prs_slides_count:
        # Add a new slide using a generic content layout from the template (e.g., layout 2)
        blank_slide_layout = prs.slide_layouts[template_layouts[2]["layout_name"]]
        prs.slides.add_slide(blank_slide_layout)
        current_prs_slides_count = len(prs.slides)

    # Fill the presentation with content
    for i, slide_info in enumerate(all_slides_content):
        if slide_info is None:
            slide_info = {"title": f"Slayd {i+1}", "content": []}

        slide = prs.slides[i]
        
        # Determine which template layout to use for this slide
        if i == 0: # Title slide
            current_template_layout = template_layouts[0]
        elif i == 1: # Plan slide
            current_template_layout = template_layouts[1]
        elif i >= 2 and i < required_total_slides - 1: # Content slides
            template_layout_index = content_slide_layouts_indices[(i-2) % len(content_slide_layouts_indices)]
            current_template_layout = template_layouts[template_layout_index]
        else: # Conclusion slide
            current_template_layout = template_layouts[7]

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
        image_query = slide_info.get("image_query", topic) if i >= 2 and i < required_total_slides - 1 else None

        # Apply content based on slide type and template layout
        if i == 0: # Title slide
            title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
            subtitle_shape = find_placeholder_by_type(slide, current_template_layout["subtitle"]["ph_type"])
            if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [topic.upper()], is_title=True)
            if subtitle_shape and name_surname: set_text_frame_content_and_style(subtitle_shape.text_frame, [name_surname.upper()], is_subtitle=True)

        elif i == 1: # Plan slide
            title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
            body_shape = find_placeholder_by_type(slide, current_template_layout["body"]["ph_type"])
            if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [plan.get("title", "Reja")], is_title=True)
            if body_shape: set_text_frame_content_and_style(body_shape.text_frame, plan.get("content", []))

        elif i == required_total_slides - 1: # Conclusion slide
            title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
            body_shape = find_placeholder_by_type(slide, current_template_layout["body"]["ph_type"])
            if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [conclusion_content.get("title", "Xulosa")], is_title=True)
            if body_shape: set_text_frame_content_and_style(body_shape.text_frame, conclusion_content.get("content", []))

        else: # Content slides (indices 2 to required_total_slides - 2)
            # Handle different content slide layouts based on template_layouts
            if current_template_layout["layout_name"] == "BLANK_1_1_1_1_1_1": # Slide 3 layout
                title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
                subtitle_shape = find_placeholder_by_type(slide, current_template_layout["subtitle"]["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [title_text], is_title=True)
                if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, content_points)
                # For text boxes, we need to find them by ID if they are not placeholders
                # This part needs more robust handling if content_points is more than 1
                # For now, we'll just use the subtitle placeholder for content

            elif current_template_layout["layout_name"] == "TITLE_AND_TWO_COLUMNS_1_1": # Slide 4 layout
                title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
                subtitle1_shape = find_placeholder_by_type(slide, current_template_layout["subtitle_1"]["ph_type"])
                subtitle2_shape = find_placeholder_by_type(slide, current_template_layout["subtitle_2"]["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [title_text], is_title=True)
                if subtitle1_shape and len(content_points) > 0: set_text_frame_content_and_style(subtitle1_shape.text_frame, [content_points[0]])
                if subtitle2_shape and len(content_points) > 1: set_text_frame_content_and_style(subtitle2_shape.text_frame, [content_points[1]])

            elif current_template_layout["layout_name"] == "ONE_COLUMN_TEXT": # Slide 5 layout
                title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
                subtitle_shape = find_placeholder_by_type(slide, current_template_layout["subtitle"]["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [title_text], is_title=True)
                if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, content_points)
                if image_query:
                    pic_placeholder = find_placeholder_by_type(slide, current_template_layout["picture"]["ph_type"])
                    if pic_placeholder:
                        add_image_to_slide(slide, image_query, pic_placeholder.left, pic_placeholder.top, pic_placeholder.width, pic_placeholder.height)
                    else:
                        add_image_to_slide(slide, image_query, Inches(7), Inches(1.5), Inches(2.5), Inches(2.5))

            elif current_template_layout["layout_name"] == "BLANK_1_1": # Slide 6 layout
                title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
                subtitle_shape = find_placeholder_by_type(slide, current_template_layout["subtitle"]["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [title_text], is_title=True)
                if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, content_points)

            elif current_template_layout["layout_name"] == "CUSTOM": # Slide 7 layout
                title_shape = find_placeholder_by_type(slide, current_template_layout["title"]["ph_type"])
                subtitle_shape = find_placeholder_by_type(slide, current_template_layout["subtitle"]["ph_type"])
                if title_shape: set_text_frame_content_and_style(title_shape.text_frame, [title_text], is_title=True)
                if subtitle_shape: set_text_frame_content_and_style(subtitle_shape.text_frame, content_points)
                if image_query:
                    pic_placeholder = find_placeholder_by_type(slide, current_template_layout["picture"]["ph_type"])
                    if pic_placeholder:
                        add_image_to_slide(slide, image_query, pic_placeholder.left, pic_placeholder.top, pic_placeholder.width, pic_placeholder.height)
                    else:
                        add_image_to_slide(slide, image_query, Inches(7), Inches(1.5), Inches(2.5), Inches(2.5))

    output_path = f"generated_presentations/{topic}_{random.randint(1000, 9999)}.pptx"
    prs.save(output_path)
    return output_path

import json
