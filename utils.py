import os
import requests
from pptx import Presentation
from pptx.util import Inches
from openai import OpenAI

# Initialize OpenAI client (Manus pre-configured)
client = OpenAI()

def search_image(query):
    """Search for an image using a public API or a simple search strategy."""
    try:
        # Using a public image API (Unsplash is a good free option for high-quality images)
        url = f"https://source.unsplash.com/featured/?{query.replace(' ', ',')}"
        response = requests.get(url, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            image_path = f"temp_image_{query.replace(' ', '_')}.jpg"
            with open(image_path, 'wb') as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        print(f"Error searching image: {e}")
    return None

def generate_presentation(topic, slide_count, template_file):
    """Generate a PowerPoint presentation based on the topic, slide count, and template."""
    template_path = os.path.join("templates/shablonlar", template_file)
    prs = Presentation(template_path)
    
    # Use GPT to generate content
    prompt = f"Create a detailed presentation outline for the topic '{topic}' with {slide_count} slides. " \
             f"For each slide, provide a 'Title', 'Content' (3-4 bullet points), and a 'Search Query' for a relevant image. " \
             f"Respond in JSON format: [{{'title': '...', 'content': ['...', '...'], 'image_query': '...'}}, ...]"
    
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    import json
    data = json.loads(response.choices[0].message.content)
    slides_data = data.get('slides', []) if 'slides' in data else list(data.values())[0]
    
    # Fill the presentation
    for i, slide_info in enumerate(slides_data[:slide_count]):
        # Use existing slide layouts if possible, otherwise add new slide
        if i < len(prs.slides):
            slide = prs.slides[i]
        else:
            slide_layout = prs.slide_layouts[1] # Title and Content layout
            slide = prs.slides.add_slide(slide_layout)
            
        # Update Title
        if slide.shapes.title:
            slide.shapes.title.text = slide_info.get('title', '')
            
        # Update Content
        content_text = "\n".join(slide_info.get('content', []))
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                shape.text = content_text
                break
                
        # Search and Add Image
        image_query = slide_info.get('image_query', topic)
        image_path = search_image(image_query)
        if image_path:
            try:
                # Add image to the slide (positioning it nicely)
                slide.shapes.add_picture(image_path, Inches(5), Inches(2), width=Inches(4))
                os.remove(image_path)
            except Exception as e:
                print(f"Error adding image to slide: {e}")
                
    output_path = f"{topic.replace(' ', '_')}.pptx"
    prs.save(output_path)
    return output_path
