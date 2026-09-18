import os
from dotenv import load_dotenv
from anthropic import Anthropic
import streamlit as st
from datetime import datetime
import json
import base64
from pathlib import Path
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from PIL import Image
import pytesseract
import PyPDF2
import requests
from urllib.parse import urlparse
import re

load_dotenv()

client = Anthropic(
    base_url=os.getenv("ANTHROPIC_BASE_URL"),
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

# Helper function for all AI calls
def ask_ai(prompt, max_tokens=2048):
    """Call Claude API with the given prompt"""
    res = client.messages.create(
        model="claude-haiku",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return res.content[0].text

# Content extraction functions
def extract_text_from_image(image_file):
    """Extract text from image using OCR"""
    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image)
        return text if text.strip() else "Image content could not be extracted via OCR"
    except Exception as e:
        return f"Error extracting text from image: {str(e)}"

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def extract_text_from_txt(txt_file):
    """Extract text from text file"""
    try:
        return txt_file.read().decode('utf-8')
    except Exception as e:
        return f"Error reading text file: {str(e)}"

def extract_content_from_url(url):
    """Extract content from URL (Google Docs, Slides, web pages, etc.)"""
    try:
        # Handle Google Docs export as text
        if 'docs.google.com/document' in url:
            export_url = url.replace('/edit', '/export?format=txt')
            response = requests.get(export_url, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                return f"Could not fetch Google Doc: {response.status_code}"

        # Handle Google Slides (convert to PDF-like content)
        elif 'docs.google.com/presentation' in url:
            return "Google Slides: Please download as PDF and upload, or convert to Google Doc for text extraction"

        # Handle regular web pages
        else:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Simple HTML to text extraction
                from html.parser import HTMLParser

                class TextExtractor(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text = []

                    def handle_data(self, data):
                        text = data.strip()
                        if text:
                            self.text.append(text)

                parser = TextExtractor()
                parser.feed(response.text)
                return '\n'.join(parser.text)
            else:
                return f"Could not fetch URL: {response.status_code}"

    except Exception as e:
        return f"Error extracting content from URL: {str(e)}"

def process_uploaded_content(uploaded_files):
    """Process uploaded files and extract content"""
    extracted_content = {}

    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        file_extension = Path(file_name).suffix.lower()

        try:
            if file_extension in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
                content = extract_text_from_image(uploaded_file)
            elif file_extension == '.pdf':
                content = extract_text_from_pdf(uploaded_file)
            elif file_extension == '.txt':
                content = extract_text_from_txt(uploaded_file)
            else:
                content = f"Unsupported file type: {file_extension}"

            extracted_content[file_name] = content
        except Exception as e:
            extracted_content[file_name] = f"Error processing file: {str(e)}"

    return extracted_content

def generate_study_guide(content_text, subject, difficulty_level):
    """Generate comprehensive study guide using Claude API"""
    prompt = f"""You are an expert study guide creator. Based on the following study material, create a comprehensive study guide.

SUBJECT: {subject}
DIFFICULTY LEVEL: {difficulty_level}

STUDY MATERIAL:
{content_text}

Please generate a study guide with the following structure (use clear markdown formatting):

# Study Guide: {subject}

## 📚 Concept Explanation
Provide a clear, detailed explanation of the main concepts. Include fill-in-the-blank sections where students complete key terms.

## ❓ Basic Comprehension Questions
Create 5-7 basic questions that test fundamental understanding. Include answers.

## 🧠 Further Understanding Questions
Create 4-6 advanced questions that require deeper analysis and critical thinking. Include answers.

## 🚀 Application Questions
Create 3-4 application/problem-solving questions that connect concepts to real-world scenarios. Include answers.

## 📝 Extra Practice Questions
Create 5-7 additional practice questions for reinforcement. Include answers.

Format each section clearly with headers and organize content for easy study and reference."""

    return ask_ai(prompt)

def generate_markdown(study_guide_content):
    """Return study guide as markdown"""
    return study_guide_content

def generate_pdf(study_guide_content, output_path):
    """Generate PDF from study guide content"""
    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=30,
            alignment=1
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2ca02c'),
            spaceAfter=12,
            spaceBefore=12
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            spaceAfter=10,
            leading=14
        )

        # Parse and add content
        lines = study_guide_content.split('\n')
        for line in lines:
            if line.startswith('# '):
                title = line.replace('# ', '').strip()
                story.append(Paragraph(title, title_style))
                story.append(Spacer(1, 12))
            elif line.startswith('## '):
                heading = line.replace('## ', '').strip()
                story.append(Paragraph(heading, heading_style))
            elif line.strip() == '':
                story.append(Spacer(1, 6))
            else:
                story.append(Paragraph(line, body_style))

        doc.build(story)
        return True
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return False

# Streamlit UI
st.set_page_config(page_title="Study Guide Generator", layout="wide", initial_sidebar_state="expanded")
st.title("📚 Study Guide Generator")
st.markdown("Generate comprehensive study guides from your course materials")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    subject = st.text_input("📖 Subject/Topic", placeholder="e.g., Biology Chapter 5: Photosynthesis")

    difficulty_level = st.select_slider(
        "📊 Difficulty Level",
        options=["Beginner", "Intermediate", "Advanced", "Expert"],
        value="Intermediate"
    )

    st.markdown("---")
    st.subheader("📤 Input Options")
    st.info("Upload study materials: Images, PDFs, or Text files")

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📥 Upload Study Materials")

    # Add tabs for file upload vs link input
    input_tab1, input_tab2 = st.tabs(["📤 Upload Files", "🔗 Paste Links"])

    with input_tab1:
        uploaded_files = st.file_uploader(
            "Choose files (images, PDFs, or text)",
            type=['png', 'jpg', 'jpeg', 'bmp', 'gif', 'pdf', 'txt'],
            accept_multiple_files=True,
            help="Upload course notes, textbook pages, lecture slides, or images"
        )

    with input_tab2:
        st.info("💡 Paste links to:\n- Google Docs (auto-extracts text)\n- Web pages\n- Other online resources")
        link_input = st.text_area(
            "Paste links (one per line)",
            height=120,
            placeholder="https://docs.google.com/document/d/...\nhttps://example.com/notes\n..."
        )

with col2:
    st.subheader("⚡ Quick Actions")
    generate_button = st.button("✨ Generate Study Guide", use_container_width=True, type="primary")
    if st.button("🔄 Clear All", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# Process content
extracted_content = {}
has_files = uploaded_files and len(uploaded_files) > 0
has_links = link_input and link_input.strip()

if generate_button and (has_files or has_links) and subject:
    total_items = (len(uploaded_files) if has_files else 0) + (len([l for l in link_input.split('\n') if l.strip()]) if has_links else 0)
    st.info(f"Processing {total_items} item(s)...")

    # Extract content from uploaded files
    if has_files:
        with st.spinner("📖 Extracting content from files..."):
            file_content = process_uploaded_content(uploaded_files)
            extracted_content.update(file_content)

    # Extract content from links
    if has_links:
        with st.spinner("🔗 Extracting content from links..."):
            links = [link.strip() for link in link_input.split('\n') if link.strip()]
            for link in links:
                try:
                    content = extract_content_from_url(link)
                    extracted_content[f"Link: {link[:50]}..."] = content
                except Exception as e:
                    extracted_content[f"Link: {link}"] = f"Error: {str(e)}"

    combined_content = "\n\n".join(extracted_content.values())

    # Generate study guide
    with st.spinner("✨ Generating study guide..."):
        study_guide = generate_study_guide(combined_content, subject, difficulty_level)

    # Display study guide
    st.success("✅ Study guide generated successfully!")
    st.markdown("---")

    # Show study guide in tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📖 Preview", "📊 Statistics", "💾 Export", "📋 Source Content"])

    with tab1:
        st.subheader("📚 Your Study Guide")
        st.markdown(study_guide)
        st.markdown("---")
        st.info("💡 Tip: Scroll down to see the full study guide, or use the Export tab to download it!")

    with tab2:
        # Calculate statistics
        lines = study_guide.split('\n')
        word_count = len(study_guide.split())
        section_count = len([l for l in lines if l.startswith('##')])
        question_count = len([l for l in lines if '?' in l])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📝 Words", word_count)
        col2.metric("📚 Sections", section_count)
        col3.metric("❓ Questions", question_count)
        col4.metric("📄 Sources", len(extracted_content))

    with tab3:
        st.subheader("Export Study Guide")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📝 Download as Markdown", use_container_width=True):
                md_content = generate_markdown(study_guide)
                st.download_button(
                    label="Download MD",
                    data=md_content,
                    file_name=f"study_guide_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

        with col2:
            if st.button("📄 Generate PDF", use_container_width=True):
                pdf_path = f"/tmp/study_guide_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                if generate_pdf(study_guide, pdf_path):
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="Download PDF",
                            data=pdf_file.read(),
                            file_name=f"study_guide_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )

        with col3:
            if st.button("📋 Copy as Text", use_container_width=True):
                st.code(study_guide, language="markdown")

        st.markdown("---")
        st.info("📌 **Note:** Google Docs export is coming soon! Currently, export as Markdown or PDF and import to Google Drive.")

    with tab4:
        st.subheader("Source Content Extracted")
        for file_name, content in extracted_content.items():
            with st.expander(f"📄 {file_name}"):
                st.text_area(f"Content from {file_name}", value=content[:500] + "..." if len(content) > 500 else content, disabled=True, height=200)

else:
    if not subject:
        st.warning("⚠️ Enter a subject to get started")
    elif not (has_files or has_links):
        st.warning("⚠️ Upload files or paste links, then click '✨ Generate Study Guide'")

    # Show example workflow
    with st.expander("💡 How to use this app"):
        st.markdown("""
        1. **Enter Subject**: Type your subject or topic in the sidebar
        2. **Set Difficulty**: Choose the appropriate difficulty level
        3. **Upload Materials**: Upload course notes, textbook pages, or images
        4. **Generate**: The app will create a comprehensive study guide
        5. **Export**: Download as Markdown, PDF, or copy the content

        ### What you'll get:
        - 📚 **Concept Explanation** with fill-in-the-blank sections
        - ❓ **Basic Comprehension Questions** with answers
        - 🧠 **Further Understanding Questions** for deep learning
        - 🚀 **Application Questions** connecting theory to practice
        - 📝 **Extra Practice Questions** for reinforcement
        """)

# Footer
st.markdown("---")
st.markdown("🤖 Powered by Claude AI | 📚 Study Guide Generator v1.0")
