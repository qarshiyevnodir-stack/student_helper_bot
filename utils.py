import os
import requests
import json
import logging
from pptx import Presentation
from pptx.util import Inches
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client (Manus pre-configured)
client = OpenAI()

def search_image(query):
    """Search for an image using Unsplash Source API."""
    try:
        # Unsplash Source API is a simple way to get a random image based on keywords
        url = f"https://source.unsplash.com/featured/?{query.replace(' ', ',')}"
        response = requests.get(url, allow_redirects=True, timeout=15)
        if response.status_code == 200:
            image_path = f"temp_{hash(query)}.jpg"
            with open(image_path, 'wb') as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        logging.error(f"Error searching image for '{query}': {e}")
    return None

def generate_presentation(topic, slide_count, template_path):
    """Generate a PowerPoint presentation based on the topic, slide count, and template."""
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
        
    prs = Presentation(template_path)
    
    # Use GPT to generate content
    prompt = f"""Create a professional presentation outline for the topic '{topic}' in Uzbek language. 
    Total slides: {slide_count}.
    For each slide, provide:
    1. 'title': A concise title.
    2. 'content': 3-4 bullet points of detailed information.
    3. 'image_query': 2-3 English keywords for a relevant image.
    
    Respond ONLY with a JSON object in this format:
    {{
      "slides": [
        {{
          "title": "Slide Title",
          "content": ["Point 1", "Point 2", "Point 3"],
          "image_query": "nature forest"
        }},
        ...
      ]
    }}"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": "You are a professional presentation creator. You write in Uzbek language."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        slides_data = data.get('slides', [])
    except Exception as e:
        logging.error(f"GPT content generation failed: {e}")
        # Fallback if GPT fails
        slides_data = [{"title": topic, "content": ["Ma'lumot topilmadi."], "image_query": topic}] * slide_count

    # Fill the presentation
    for i, slide_info in enumerate(slides_data[:slide_count]):
        # If we run out of slides in template, add a new one using the first layout
        if i < len(prs.slides):
            slide = prs.slides[i]
        else:
            slide_layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
            slide = prs.slides.add_slide(slide_layout)
            
        # Update Title
        if slide.shapes.title:
            slide.shapes.title.text = slide_info.get('title', '')
            
        # Update Content (finding the largest text box that is not the title)
        content_text = "\n".join(slide_info.get('content', []))
        body_shape = None
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                # Simple heuristic: the largest non-title text box is usually the body
                if body_shape is None or (shape.width * shape.height > body_shape.width * body_shape.height):
                    body_shape = shape
        
        if body_shape:
            body_shape.text = content_text
                
        # Search and Add Image
        image_query = slide_info.get('image_query', topic)
        image_path = search_image(image_query)
        if image_path:
            try:
                # Add image to the slide (positioning it on the right side)
                # This is a generic position, might need adjustment per template
                slide.shapes.add_picture(image_path, Inches(6), Inches(1.5), width=Inches(3.5))
                os.remove(image_path)
            except Exception as e:
                logging.error(f"Error adding image to slide {i}: {e}")
                
    output_filename = f"temp_output_{hash(topic)}.pptx"
    prs.save(output_filename)
    return output_filename
