import os
from pptx import Presentation
from pptx.util import Inches
from openai import OpenAI

async def generate_slide_content(openai_api_key: str, topic: str, slides_count: int) -> list:
    client = OpenAI(api_key=openai_api_key)

    prompt = f"Generate {slides_count} detailed slide titles and content for a presentation on the topic: \'{topic}\'.\n\nEach slide should have a title and a content section of 500-800 characters. Format the output as a JSON array of objects, where each object has 'title' and 'content' keys. Ensure the content is academic, analytical, and comprehensive. Example: [{{'title': 'Slide 1 Title', 'content': 'Slide 1 Content'}}, {{'title': 'Slide 2 Title', 'content': 'Slide 2 Content'}}]."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a helpful assistant designed to output JSON."}, 
            {"role": "user", "content": prompt}
        ]
    )
    
    # Assuming the response content is a JSON string containing a list of slide objects
    import json
    try:
        slide_data = json.loads(response.choices[0].message.content)
        # The API might return a single object with a key like 'slides' that contains the array
        if isinstance(slide_data, dict) and 'slides' in slide_data:
            return slide_data['slides']
        elif isinstance(slide_data, list):
            return slide_data
        else:
            raise ValueError("Unexpected JSON structure from OpenAI.")
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Raw response content: {response.choices[0].message.content}")
        raise

def create_presentation(template_id: int, slide_contents: list, output_path: str):
    template_path = f"templates/template{template_id}.pptx"
    if not os.path.exists(template_path):
        # Create a dummy template if not found
        prs = Presentation()
        prs.save(template_path)

    prs = Presentation(template_path)

    for i, slide_data in enumerate(slide_contents):
        title = slide_data.get("title", f"Slide {i+1} Title")
        content = slide_data.get("content", f"Slide {i+1} Content")

        # Use a blank slide layout for simplicity if template layouts are complex
        # Or try to find a suitable layout
        slide_layout = prs.slide_layouts[6] # Often a blank slide layout
        if len(prs.slide_layouts) > 1: # Try to find a title and content layout
            for layout in prs.slide_layouts:
                if layout.name == "Title and Content":
                    slide_layout = layout
                    break
                elif layout.name == "Title Slide" and i == 0:
                    slide_layout = layout
                    break

        slide = prs.slides.add_slide(slide_layout)

        # Add title
        if slide.shapes.title:
            slide.shapes.title.text = title
        else:
            left = top = width = height = Inches(1)
            txBox = slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.text = title

        # Add content
        # Find a placeholder for body text, or add a new text box
        body_placeholder = None
        for shape in slide.shapes:
            if shape.has_text_frame and shape.is_placeholder and 'body' in shape.name.lower():
                body_placeholder = shape
                break
        
        if body_placeholder:
            tf = body_placeholder.text_frame
            tf.clear()
            p = tf.paragraphs[0]
            p.text = content
        else:
            left = Inches(1)
            top = Inches(2)
            width = Inches(8)
            height = Inches(4.5)
            txBox = slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.text = content

    prs.save(output_path)


