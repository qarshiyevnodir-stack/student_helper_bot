import os
import requests
import json
import logging
import random
from pptx import Presentation
from pptx.util import Inches
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
        seed = random.randint(1, 1000)
        url = f"https://source.unsplash.com/featured/?{query.replace(\' \', \',\')}&sig={seed}"
        response = requests.get(url, allow_redirects=True, timeout=15)
        if response.status_code == 200:
            image_path = f"temp_{hash(query)}_{seed}.jpg"
            with open(image_path, \'wb\') as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        logging.error(f"Error searching image for \'{query}\': {e}")
    return None

def generate_slide_content(topic, slide_number, total_slides):
    """Generate content for a slide using an LLM."""
    prompt = f"""Create a professional presentation outline for the topic \'{topic}\' in Uzbek language. \n"
    prompt += f"Total slides: {total_slides}. This is slide number {slide_number}.\n"
    prompt += f"For this slide, provide:\n"
    prompt += f"1. \'title\': A concise title.\n"
    prompt += f"2. \'content\': 3-4 bullet points of detailed information.\n"
    prompt += f"3. \'image_query\': 2-3 English keywords for a relevant image.\n"
    prompt += f"\n"
    prompt += f"Respond ONLY with a JSON object in this format:\n"
    prompt += f"{{\n"
    prompt += f"  \"title\": \"Slayd sarlavhasi\",\n"
    prompt += f"  \"content\": [\"Ma\'lumot 1\", \"Ma\'lumot 2\", \"Ma\'lumot 3\"],\n"
    prompt += f"  \"image_query\": \"technology computer\"\n"
    prompt += f"}}"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": "You are a professional presentation creator. You write in Uzbek language."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        return data
    except Exception as e:
        logging.error(f"GPT content generation failed for slide {slide_number}: {e}")
        return {"title": f"{topic} - Slayd {slide_number}", "content": ["Ma\'lumot topilmadi."], "image_query": topic}

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
                if text_frame.paragraphs:
                    first_paragraph = text_frame.paragraphs[0]
                    if first_paragraph.runs:
                        first_run = first_paragraph.runs[0]
                        original_styles[shape.shape_id] = {
                            'font_name': first_run.font.name,
                            'font_size': first_run.font.size,
                            'font_color': first_run.font.color.rgb if first_run.font.color.rgb else None,
                            'bold': first_run.font.bold,
                            'italic': first_run.font.italic
                        }

        # Clear all existing text and images
        for shape in list(slide.shapes): # Iterate over a copy to allow deletion
            if shape.has_text_frame:
                shape.text_frame.clear()
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                sp = shape._element
                sp.getparent().remove(sp)
        
        # A. Update Title and Content
        title_text = slide_info.get('title', '')
        content_points = slide_info.get('content', [])
        body_text = "\n".join(content_points)

        # Find suitable text frames for title and body, or add new ones
        title_shape = None
        body_shape = None

        for shape in slide.shapes:
            if shape.has_text_frame:
                if shape.is_placeholder and 'title' in shape.name.lower():
                    title_shape = shape
                elif shape.is_placeholder and ('body' in shape.name.lower() or 'content' in shape.name.lower()):
                    body_shape = shape
                elif not title_shape and shape.text_frame.text == "": # Fallback for empty text frames
                    title_shape = shape
                elif not body_shape and shape.text_frame.text == "": # Fallback for empty text frames
                    body_shape = shape
        
        # If no placeholders, add generic text boxes
        if not title_shape:
            left, top, width, height = Inches(1), Inches(0.5), Inches(8), Inches(1)
            title_shape = slide.shapes.add_textbox(left, top, width, height)
        if not body_shape:
            left, top, width, height = Inches(1), Inches(1.5), Inches(8), Inches(5)
            body_shape = slide.shapes.add_textbox(left, top, width, height)

        # Apply new text and preserve original styles
        if title_shape:
            text_frame = title_shape.text_frame
            p = text_frame.paragraphs[0]
            run = p.add_run()
            run.text = title_text
            if title_shape.shape_id in original_styles:
                style = original_styles[title_shape.shape_id]
                run.font.name = style['font_name']
                run.font.size = style['font_size']
                if style['font_color']: run.font.color.rgb = style['font_color']
                run.font.bold = style['bold']
                run.font.italic = style['italic']

        if body_shape:
            text_frame = body_shape.text_frame
            p = text_frame.paragraphs[0]
            run = p.add_run()
            run.text = body_text
            if body_shape.shape_id in original_styles:
                style = original_styles[body_shape.shape_id]
                run.font.name = style['font_name']
                run.font.size = style['font_size']
                if style['font_color']: run.font.color.rgb = style['font_color']
                run.font.bold = style['bold']
                run.font.italic = style['italic']

        # C. Replace Images
        image_query = slide_info.get('image_query', topic)
        new_image_path = search_image(image_query)
        
        if new_image_path:
            try:
                # Find existing picture placeholders or add to a default position
                picture_placeholder = None
                for shape in slide.shapes:
                    if shape.is_placeholder and shape.has_text_frame is False: # Look for non-text placeholders
                        picture_placeholder = shape
                        break
                
                if picture_placeholder:
                    left, top, width, height = picture_placeholder.left, picture_placeholder.top, picture_placeholder.width, picture_placeholder.height
                    slide.shapes.add_picture(new_image_path, left, top, width=width, height=height)
                    sp = picture_placeholder._element
                    sp.getparent().remove(sp) # Remove old placeholder
                else:
                    # If no suitable placeholder, add it to a default position (right side)
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
