
import os
import threading
import queue
import subprocess
import ast
import configparser
import time
import re
import shutil
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext
from pathlib import Path

# Third-party imports
from PIL import Image, ImageTk

# pip install google-genai Pillow
try:
    from google import genai
    from google.genai import types
    GENAI_IMPORTED = True
except ImportError:
    GENAI_IMPORTED = False

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
CONFIG_PATH = Path('config.ini')
VM_DIR = Path('vm')
TRASH_DIR_NAME = ".trash" # For storing discarded images
APP_TITLE = "Enhanced Multi-Agent IDE"
TEXT_MODEL_NAME = "gemini-2.5-flash-preview-05-20"
IMAGE_MODEL_NAME = "gemini-2.0-flash-preview-image-generation"

# Enhanced Agent System Prompts with Grading System
MAIN_AGENT_PROMPT = """You are the PRIMARY CODER AGENT in an advanced multi-agent IDE system. Your role is to implement code, execute commands, and coordinate with other agents.

**ENVIRONMENT:**
You operate in a headless environment with full vision capabilities. You can analyze images, understand visual content, and make informed coding decisions based on visual context.

**COMMANDS:**
- `create_file(path, content)`: Creates a new text file with specified content.
- `write_to_file(path, content)`: Overwrites an existing text file.
- `delete_file(path)`: Deletes a file or directory.
- `rename_file(old_path, new_path)`: Renames a file or directory.
- `run_command(command)`: Executes a shell command in the project directory.
- `generate_image(path, prompt)`: Generates an image using AI based on a text prompt.

**ENHANCED CAPABILITIES:**
- **Vision Analysis**: Can analyze existing images to inform coding decisions
- **Image Generation**: Can create images when requested by users
- **Code Integration**: Seamlessly integrates visual assets into code projects
- **Multi-format Support**: Handles text, images, and mixed-media projects
- **Quality Focus**: Strive for excellence as your work will be graded by critique agents

**RULES:**
1. **COMMAND ONLY OUTPUT**: Your response must ONLY contain commands wrapped in backticks.
2. **PROPER QUOTING**: All string arguments must be in single quotes.
3. **MULTILINE CONTENT**: Use triple quotes for file content spanning multiple lines.
4. **NO COMMENTARY**: Never output explanatory text outside backticked commands.
5. **VISUAL AWARENESS**: Consider existing images when making implementation decisions.
6. **COLLABORATION**: Work with Code Critic and Art Critic for optimal results.
7. **QUALITY EXCELLENCE**: Aim for high-quality implementation as critique agents will grade your work.
8. **IMAGE GENERATION VARIATIONS**: When tasked with generating an image, you MUST generate three distinct variations. For each variation, issue a separate `generate_image(path, prompt)` command. Use unique, descriptive filenames (e.g., `image_v1.png`, `image_v2.png`, `image_v3.png`). If possible, subtly vary the prompts for each of the three images to encourage diversity, while adhering to the core user request and any artistic guidance provided.
9. **USE RENAME_FILE**: Always use the `rename_file(old_path, new_path)` command for renaming files or directories. Do not use `run_command` with `mv` or `ren` for renaming.

**INTERACTION FLOW:**
1. Implement user requests through commands with highest quality standards
2. Generate images when visual content is needed
3. Create comprehensive solutions that may include both code and visual assets
4. Accept feedback gracefully and improve upon critiques
"""

CRITIC_AGENT_PROMPT = """You are the CODE CRITIQUE AGENT in an advanced multi-agent IDE system. Your enhanced role includes code review, security analysis, performance optimization, and GRADING the Main Coder's work.

**GRADING RESPONSIBILITIES:**
You must provide a numerical grade (0-100) for the Main Coder's implementation based on:
- **Code Quality (25%)**: Structure, readability, maintainability
- **Security (25%)**: Vulnerability assessment, safe practices
- **Performance (25%)**: Efficiency, optimization, scalability
- **Best Practices (25%)**: Standards compliance, documentation, error handling

**GRADING SCALE:**
- 90-100: Excellent - Outstanding implementation with minimal issues
- 80-89: Good - Solid work with minor improvements needed
- 70-79: Satisfactory - Adequate but needs some improvements
- 60-69: Needs Improvement - Significant issues that should be addressed
- Below 60: Poor - Major problems requiring complete rework

**ENHANCED RESPONSIBILITIES:**
- **Code Quality Analysis**: Review code structure, readability, and maintainability
- **Security Assessment**: Identify potential security vulnerabilities and suggest fixes
- **Performance Optimization**: Recommend performance improvements and efficient algorithms
- **Best Practices Enforcement**: Ensure adherence to coding standards and conventions
- **Architecture Review**: Suggest better design patterns and system architecture
- **Testing Strategy**: Recommend testing approaches and identify untested code paths
- **Documentation Review**: Ensure code is properly documented and self-explanatory

**MANDATORY RESPONSE FORMAT:**
Start your response with: **GRADE: [score]/100**
Then provide structured feedback with:
- **Priority Level**: Critical, High, Medium, Low
- **Category**: Security, Performance, Maintainability, etc.
- **Specific Issue**: Clear description of the problem
- **Recommended Solution**: Actionable steps to resolve the issue
- **Code Examples**: When helpful, provide improved code snippets

**GRADING CRITERIA:**
Be thorough but fair in your assessment. Consider the complexity of the task and provide constructive feedback that helps the Main Coder improve.
"""

ART_AGENT_PROMPT = """You are the ART CRITIQUE AGENT in an advanced multi-agent IDE system with SUPERIOR VISION CAPABILITIES. You specialize in visual analysis, artistic guidance, and GRADING visual/design work.

**GRADING RESPONSIBILITIES:**
You must provide a numerical grade (0-100) for visual and design work based on:
- **Visual Composition (25%)**: Balance, hierarchy, rule of thirds, contrast
- **Color Theory (25%)**: Harmony, psychology, accessibility, consistency
- **User Experience (25%)**: Usability, accessibility, user flow
- **Technical Quality (25%)**: Resolution, file formats, optimization

**GRADING SCALE:**
- 90-100: Excellent - Outstanding visual design with professional quality
- 80-89: Good - Strong design with minor aesthetic improvements needed
- 70-79: Satisfactory - Adequate design but needs visual enhancements
- 60-69: Needs Improvement - Significant design issues affecting usability
- Below 60: Poor - Major visual problems requiring complete redesign

**ENHANCED VISION CAPABILITIES:**
- **Image Analysis**: Deep understanding of visual composition, color theory, and design principles
- **Style Recognition**: Identify artistic styles, design patterns, and visual trends
- **UI/UX Evaluation**: Assess user interface design and user experience elements
- **Visual Consistency**: Ensure consistent visual branding across project assets
- **Accessibility Review**: Check visual accessibility and inclusive design practices

**MANDATORY RESPONSE FORMAT:**
Start your response with: **GRADE: [score]/100**
Then provide comprehensive artistic guidance including:
- **Visual Assessment**: Analysis of current visual elements
- **Design Recommendations**: Specific suggestions for improvement
- **Technical Specifications**: Color codes, dimensions, file formats
- **Image Generation Prompts**: Detailed, optimized prompts for AI image creation
- **Implementation Notes**: Technical considerations for developers

**GRADING CRITERIA:**
Assess both aesthetic quality and functional usability. Consider accessibility, user experience, and technical implementation quality.
"""

PROACTIVE_ART_AGENT_PROMPT = """You are the ART CRITIQUE AGENT, acting in a PROACTIVE GUIDANCE role.
Your task is to help the Main Coder Agent generate a high-quality image by providing artistic direction *before* generation.
Analyze the following user request and provide:
1.  **Suggested Art Style(s):** (e.g., photorealistic, impressionistic, anime, cyberpunk)
2.  **Mood and Tone:** (e.g., serene, energetic, mysterious, whimsical)
3.  **Key Visual Elements:** (e.g., dominant subjects, important background features)
4.  **Color Palette Suggestions:** (e.g., warm tones, monochrome, vibrant contrasting colors, specific hex codes if applicable)
5.  **Compositional Ideas:** (e.g., rule of thirds, leading lines, specific camera angles)
6.  **Keywords for Image Generation:** (A list of potent keywords)
7.  **Optimized Image Generation Prompt for Coder:** (A complete, detailed prompt the Main Coder can use)

USER REQUEST:
{{USER_REQUEST}}

Provide your guidance clearly and concisely. Do not grade.
"""

PROMPT_ENHANCER_AGENT_PROMPT = """You are a PROMPT ENHANCER AGENT. Your role is to take a user's raw prompt and transform it into a more detailed, specific, and well-structured prompt that is optimized for large language models (LLMs) and image generation models. Your *sole* responsibility is to refine and rephrase the user's input to be a better prompt for a different AI. You do not answer or execute any part of the user's request.

**TASK:**
Rewrite the given user prompt to maximize its effectiveness. Consider the following:
1.  **Clarity and Specificity:** Add details that make the request unambiguous. For example, if the user asks for "a cat image," you might enhance it to "a photorealistic image of a fluffy ginger tabby cat lounging in a sunbeam."
2.  **Context:** If the user's prompt is for coding, ensure the enhanced prompt specifies language, libraries, and desired functionality. For example, "python script for web server" could become "Create a Python script using the Flask framework to implement a simple web server with a single endpoint '/' that returns 'Hello, World!'."
3.  **Structure:** Organize the prompt logically. Use bullet points or numbered lists for complex requests.
4.  **Keywords:** Include relevant keywords that the LLM can use to generate a better response.
5.  **Tone and Style:** Maintain the user's original intent but refine the language to be more effective for AI. For image generation, suggest artistic styles (e.g., "impressionistic style", "cyberpunk aesthetic", "shot on 35mm film").
6.  **Completeness:** Ensure the prompt contains all necessary information for the AI to perform the task well.
7.  **Self-Improvement/Meta-Modification Requests:** If the user's prompt is a request for the AI system to improve itself, its own code (e.g., the Python code of this application), or its capabilities, reformulate this into an actionable prompt for a *coding agent*. This enhanced prompt should direct the coding agent to:
    a. Analyze its current codebase (which it should have access to, particularly files like `gemini_app.py` if mentioned or implied).
    b. Identify specific areas for improvement based on the user's request (e.g., refactoring for efficiency, adding a new feature, improving error handling, enhancing comments or documentation).
    c. Implement these improvements by generating commands to modify its own code files. Ensure the prompt specifies which files to modify if known.

**RULES:**
1.  **CRITICALLY IMPORTANT: OUTPUT ONLY THE ENHANCED PROMPT:** Your response *must exclusively* contain the refined prompt text and nothing else. Do not include any explanations, apologies, conversational filler, or any attempt to answer or execute the user's underlying request. Your job is *only* to improve the prompt for another AI.
2.  **MAINTAIN INTENT:** Do not change the core meaning or goal of the user's original request.
3.  **BE CONCISE BUT THOROUGH:** The enhanced prompt should be detailed but not overly verbose.
4.  **DO NOT ANSWER:** Under no circumstances should you attempt to answer or fulfill the request described in the user's prompt. Your only task is to make the prompt itself better for a subsequent AI agent.

**EXAMPLE (Image Generation):**
User Prompt: "dog playing"
Enhanced Prompt: "A high-resolution digital painting of a golden retriever puppy playfully chasing a red ball across a sunlit grassy field, with a shallow depth of field effect. Art style: Disney Pixar."

**EXAMPLE (Code Generation):**
User Prompt: "make a button in html"
Enhanced Prompt: "Create an HTML snippet for a button with the text 'Click Me'. The button should have a blue background, white text, rounded corners (border-radius: 5px), and a subtle box-shadow. When clicked, it should execute a JavaScript function called 'handleButtonClick()'."

Now, enhance the following user prompt:
"""

def load_api_key():
    """Load API key from environment or config file"""
    if "GEMINI_API_KEY" in os.environ:
        return os.environ["GEMINI_API_KEY"]

    config = configparser.ConfigParser()
    if CONFIG_PATH.exists():
        config.read(CONFIG_PATH)
        return config.get('API', 'key', fallback=None)
    return None

def save_api_key(key):
    """Save API key to config file"""
    config = configparser.ConfigParser()
    config['API'] = {'key': key}
    with open(CONFIG_PATH, 'w') as f:
        config.write(f)

# -----------------------------------------------------------------------------
# Enhanced Multi-Agent System
# -----------------------------------------------------------------------------
class EnhancedMultiAgentSystem:
    def __init__(self, api_key):
        if not GENAI_IMPORTED:
            raise ImportError("google-genai not installed")

        self.client = genai.Client(api_key=api_key)
        self.conversation_history = []
        self.error_context = []
        self.project_context = {"files": [], "images": [], "recent_changes": []}
        self.grading_enabled = True
        self.prompt_enhancer_enabled = True
        self.max_retry_attempts = 3
        self.current_attempt = 0
        
        self.command_handlers = {
            "create_file": self._create_file,
            "write_to_file": self._write_to_file,
            "delete_file": self._delete_file,
            "run_command": self._run_command,
            "generate_image": self.generate_image,
            "rename_file": self._rename_file,
        }

    def _rename_file(self, old_path_str: str, new_path_str: str) -> str:
        """Renames a file or directory."""
        old_safe_path = self._safe_path(old_path_str)
        if not old_safe_path:
            return f"❌ Invalid old path: {old_path_str}"

        new_safe_path = self._safe_path(new_path_str)
        if not new_safe_path:
            return f"❌ Invalid new path: {new_path_str}"

        if not old_safe_path.exists():
            return f"❌ Source path does not exist: {old_path_str}"

        try:
            new_safe_path.parent.mkdir(parents=True, exist_ok=True)
            os.rename(old_safe_path, new_safe_path)
            return f"✅ Renamed: {old_path_str} to {new_path_str}"
        except Exception as e:
            error_msg = f"❌ Error renaming {old_path_str}: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def _get_enhanced_prompt(self, user_prompt):
        """Calls the PROMPT_ENHANCER_AGENT to refine the user's prompt and streams the response."""
        try:
            prompt_parts = [{"text": f"{PROMPT_ENHANCER_AGENT_PROMPT}\n\n{user_prompt}"}]
            response_stream = self.client.models.generate_content_stream(
                model=TEXT_MODEL_NAME,
                contents=prompt_parts
            )
            for chunk in response_stream:
                yield chunk.text
        except Exception as e:
            self.error_context.append(f"Prompt Enhancer Error: {e}")
            # Fallback to original prompt if enhancer fails (as a single yield)
            yield user_prompt

    def _handle_prompt_enhancement(self, original_user_prompt):
        """Handles the prompt enhancement phase, consuming the stream."""
        if self.prompt_enhancer_enabled:
            yield {"type": "system", "content": "✨ Enhancing prompt..."}
            yield {"type": "agent_status_update", "agent": "prompt_enhancer", "status": "active"}

            enhanced_prompt_chunks = []
            full_enhanced_prompt = ""
            try:
                for chunk_text in self._get_enhanced_prompt(original_user_prompt):
                    enhanced_prompt_chunks.append(chunk_text)
                    yield {"type": "agent_stream_chunk", "agent": "✨ Prompt Enhancer", "content": chunk_text}
                full_enhanced_prompt = "".join(enhanced_prompt_chunks)
            except Exception as e:
                # Error already logged by _get_enhanced_prompt, here we ensure fallback
                full_enhanced_prompt = original_user_prompt
                yield {"type": "error", "content": f"Prompt Enhancer stream failed, falling back: {e}"}


            self._log_interaction("prompt_enhancer", full_enhanced_prompt) # Log the complete text
            yield {"type": "agent_status_update", "agent": "prompt_enhancer", "status": "inactive"}
            # Removed: yield {"type": "agent", "agent": "✨ Prompt Enhancer", "content": full_enhanced_prompt}
            return full_enhanced_prompt
        else:
            yield {"type": "system", "content": "✨ Prompt enhancer disabled. Using original prompt."}
            return original_user_prompt

    def _handle_proactive_art_guidance(self, enhanced_user_prompt):
        """Handles the proactive art guidance phase."""
        proactive_art_advice = None
        if self._should_invoke_art_critic(enhanced_user_prompt, "", [], mode="proactive"):
            yield {"type": "system", "content": "🎨 Art Critic providing initial guidance..."}
            yield {"type": "agent_status_update", "agent": "art_critic_proactive", "status": "active"}

            proactive_art_advice_chunks = []
            full_proactive_art_advice = ""
            try:
                if hasattr(self, "_get_proactive_art_guidance"):
                    for chunk_text in self._get_proactive_art_guidance(enhanced_user_prompt):
                        proactive_art_advice_chunks.append(chunk_text)
                        yield {"type": "agent_stream_chunk", "agent": "🎨 Art Critic (Proactive)", "content": chunk_text}
                    full_proactive_art_advice = "".join(proactive_art_advice_chunks)

                    # Logging is handled by _get_proactive_art_guidance itself after stream completion
                    if full_proactive_art_advice and full_proactive_art_advice.startswith("Error generating proactive art guidance"):
                         yield {"type": "error", "content": f"Proactive Art Critic failed: {full_proactive_art_advice}"}
                    # The full message yield is removed as per instructions.
                else:
                    yield {"type": "system", "content": "🔧 Note: _get_proactive_art_guidance method not yet implemented."}
                    full_proactive_art_advice = "Proactive art guidance method not implemented." # for return value
            except AttributeError:
                 yield {"type": "system", "content": "🔧 Note: _get_proactive_art_guidance method not yet implemented (AttributeError)."}
                 full_proactive_art_advice = "Proactive art guidance method not implemented (AttributeError)." # for return value
            except Exception as e:
                full_proactive_art_advice = f"Error processing proactive art guidance stream: {e}"
                self._log_interaction("proactive_art_critic", full_proactive_art_advice) # Log error
                yield {"type": "error", "content": full_proactive_art_advice}
            finally:
                yield {"type": "agent_status_update", "agent": "art_critic_proactive", "status": "inactive"}
            proactive_art_advice = full_proactive_art_advice # Set the return value
        return proactive_art_advice

    def _execute_main_coder_phase(self, current_main_coder_prompt, proactive_art_advice, attempt_suffix):
        """Executes the main coder's implementation phase."""
        yield {"type": "system", "content": f"🚀 Main Coder Agent analyzing and implementing...{attempt_suffix}"}
        yield {"type": "agent_status_update", "agent": "main_coder", "status": "active"}

        main_prompt_parts = self._build_enhanced_prompt(
            current_main_coder_prompt,
            MAIN_AGENT_PROMPT,
            proactive_art_advice=proactive_art_advice
        )

        main_response_stream = self.client.models.generate_content_stream(
            model=TEXT_MODEL_NAME,
            contents=main_prompt_parts
        )

        accumulated_main_response_text = ""
        for chunk in main_response_stream:
            if chunk.text: # Ensure there's text content
                accumulated_main_response_text += chunk.text
                yield {"type": "agent_stream_chunk", "agent": "🤖 Main Coder", "content": chunk.text}

        yield {"type": "agent_status_update", "agent": "main_coder", "status": "inactive"}

        self._log_interaction("user", current_main_coder_prompt) # Log original prompt
        self._log_interaction("main_coder", accumulated_main_response_text) # Log accumulated response

        # Yield the full response as one message after streaming, for non-streaming consumers or display
        # yield {"type": "agent", "agent": "🤖 Main Coder", "content": accumulated_main_response_text} # This might be redundant if chat display handles chunks

        if accumulated_main_response_text.count("`generate_image(") >= 2:
            yield {"type": "system", "content": "ℹ️ Main Coder is generating multiple image variations..."}

        implementation_results = []
        generated_image_paths_batch = []
        for result in self._process_enhanced_commands(accumulated_main_response_text): # Use accumulated text
            implementation_results.append(result)
            yield result
            if result.get("type") == "file_changed":
                file_path_str = result.get("content", "")
                if file_path_str.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    # Ensure the path is within the VM_DIR for safety, before appending
                    safe_file_path = self._safe_path(Path(file_path_str).name) # Check against base name if path is complex
                    if safe_file_path and Path(file_path_str).parent.name == VM_DIR.name or \
                       (Path(file_path_str).parent.parent.name == VM_DIR.name if Path(file_path_str).parent.name else False): # Handle cases like vm/subdir/img.png
                        generated_image_paths_batch.append(str(Path(VM_DIR) / Path(file_path_str).relative_to(VM_DIR))) # Store a clean, project-relative path

        return accumulated_main_response_text, implementation_results, generated_image_paths_batch

    def _perform_critic_evaluations(self, original_user_prompt, main_response_text, implementation_results, generated_image_paths_batch):
        """Performs evaluations by Code Critic and Art Critic."""
        critic_grade = None
        all_art_critiques = []
        best_image_details = None
        final_art_grade_for_overall_calc = None

        should_use_critic = self._should_invoke_code_critic(original_user_prompt, main_response_text, implementation_results)
        # Reactive call, defaults to mode="reactive"
        should_use_art_critic = self._should_invoke_art_critic(original_user_prompt, main_response_text, implementation_results)

        if should_use_critic and self.grading_enabled:
            yield {"type": "system", "content": "🔍 Code Critic Agent performing deep analysis and grading..."}
            yield {"type": "agent_status_update", "agent": "code_critic", "status": "active"}

            critic_analysis_chunks = []
            full_critic_analysis = ""
            try:
                for chunk_text in self._get_code_critique(original_user_prompt, main_response_text, implementation_results):
                    critic_analysis_chunks.append(chunk_text)
                    yield {"type": "agent_stream_chunk", "agent": "📊 Code Critic", "content": chunk_text}
                full_critic_analysis = "".join(critic_analysis_chunks)
                self._log_interaction("code_critic", full_critic_analysis) # Log complete text
            except Exception as e:
                full_critic_analysis = f"Error processing code critique stream: {e}"
                self._log_interaction("code_critic", full_critic_analysis) # Log error
                # No need to append to self.error_context here as _get_code_critique already does

            yield {"type": "agent_status_update", "agent": "code_critic", "status": "inactive"}
            if full_critic_analysis and not full_critic_analysis.startswith("Error generating code critique"):
                # Removed: yield {"type": "agent", "agent": "📊 Code Critic", "content": full_critic_analysis}
                critic_grade = self._extract_grade(full_critic_analysis)
            elif full_critic_analysis: # It's an error message from the stream
                 yield {"type": "error", "content": f"Code Critic failed: {full_critic_analysis}"}


        if self.grading_enabled and generated_image_paths_batch:
            yield {"type": "system", "content": "🎨 Art Critic Agent analyzing generated visual elements and grading (batch)..."}
            yield {"type": "agent_status_update", "agent": "art_critic", "status": "active"}
            for i, image_path in enumerate(generated_image_paths_batch):
                image_filename = os.path.basename(str(image_path))
                yield {"type": "system", "content": f"🎨 Art Critic evaluating image: {image_filename} ({i+1}/{len(generated_image_paths_batch)})..."}

                art_analysis_chunks = []
                full_art_analysis_single = ""
                try:
                    for chunk_text in self._get_art_critique(original_user_prompt, main_response_text, implementation_results, target_image_path=str(image_path)):
                        art_analysis_chunks.append(chunk_text)
                        yield {"type": "agent_stream_chunk", "agent": f"🎭 Art Critic ({image_filename})", "content": chunk_text}
                    full_art_analysis_single = "".join(art_analysis_chunks)
                    self._log_interaction(f"art_critic_{image_filename}", full_art_analysis_single) # Log complete text
                except Exception as e:
                    full_art_analysis_single = f"Error processing art critique stream for {image_filename}: {e}"
                    self._log_interaction(f"art_critic_{image_filename}", full_art_analysis_single)

                if full_art_analysis_single and not full_art_analysis_single.startswith("Error generating art critique"):
                    current_art_grade = self._extract_grade(full_art_analysis_single)
                    all_art_critiques.append({"image_path": str(image_path), "critique_text": full_art_analysis_single, "grade": current_art_grade})
                    # Removed: yield {"type": "agent", "agent": f"🎭 Art Critic ({image_filename})", "content": full_art_analysis_single}
                elif full_art_analysis_single:
                    yield {"type": "error", "content": f"Art Critic failed for {image_filename}: {full_art_analysis_single}"}

            yield {"type": "agent_status_update", "agent": "art_critic", "status": "inactive"}
        elif should_use_art_critic and self.grading_enabled:
            yield {"type": "system", "content": "🎨 Art Critic Agent analyzing visual elements (general)..."}
            yield {"type": "agent_status_update", "agent": "art_critic", "status": "active"}

            art_analysis_general_chunks = []
            full_art_analysis_general = ""
            try:
                for chunk_text in self._get_art_critique(original_user_prompt, main_response_text, implementation_results, target_image_path=None):
                    art_analysis_general_chunks.append(chunk_text)
                    yield {"type": "agent_stream_chunk", "agent": "🎭 Art Critic", "content": chunk_text}
                full_art_analysis_general = "".join(art_analysis_general_chunks)
                self._log_interaction("art_critic_general", full_art_analysis_general)
            except Exception as e:
                full_art_analysis_general = f"Error processing general art critique stream: {e}"
                self._log_interaction("art_critic_general", full_art_analysis_general)

            yield {"type": "agent_status_update", "agent": "art_critic", "status": "inactive"}
            if full_art_analysis_general and not full_art_analysis_general.startswith("Error generating art critique"):
                current_art_grade_general = self._extract_grade(full_art_analysis_general)
                all_art_critiques.append({"image_path": "general_critique", "critique_text": full_art_analysis_general, "grade": current_art_grade_general})
                # Removed: yield {"type": "agent", "agent": "🎭 Art Critic", "content": full_art_analysis_general}
            elif full_art_analysis_general:
                yield {"type": "error", "content": f"General Art Critic failed: {full_art_analysis_general}"}

        highest_art_grade = -1
        if all_art_critiques:
            for critique_item in all_art_critiques:
                current_grade = critique_item.get('grade')
                if current_grade is not None and current_grade > highest_art_grade:
                    highest_art_grade = current_grade
                    best_image_details = critique_item
            if best_image_details:
                yield {"type": "system", "content": f"🏆 Selected '{os.path.basename(best_image_details['image_path'])}' as the best image with a grade of {best_image_details['grade']}/100."}
                final_art_grade_for_overall_calc = best_image_details['grade']
            else:
                yield {"type": "system", "content": "ℹ️ No best image could be determined from the batch (no valid grades)."}
        elif generated_image_paths_batch: # Images generated but not graded
             yield {"type": "system", "content": "ℹ️ Images were generated but not graded by Art Critic."}


        return critic_grade, all_art_critiques, best_image_details, final_art_grade_for_overall_calc

    def _handle_retry_and_finalization(self, original_user_prompt, current_main_coder_prompt_ref_for_retry, # Pass as a list to modify
                                       critic_grade, all_art_critiques, best_image_details,
                                       final_art_grade_for_overall_calc, generated_image_paths_batch,
                                       main_response_text, implementation_results): # Added main_response_text, implementation_results
        """Handles the retry logic, image trashing, and final messages."""
        perform_retry = False
        retry_reason_message = ""
        art_grade_display = final_art_grade_for_overall_calc if final_art_grade_for_overall_calc is not None else "N/A"
        overall_grade = self._calculate_overall_grade(critic_grade, final_art_grade_for_overall_calc)

        if self.grading_enabled and generated_image_paths_batch and any(cq.get('grade') is not None for cq in all_art_critiques):
            num_graded_batch_images = 0
            failing_batch_images_count = 0
            for critique_item in all_art_critiques:
                if critique_item.get('image_path') in generated_image_paths_batch and critique_item.get('grade') is not None:
                    num_graded_batch_images += 1
                    if critique_item.get('grade') < 70:
                        failing_batch_images_count += 1
            if num_graded_batch_images > 0 and num_graded_batch_images == failing_batch_images_count:
                perform_retry = True
                retry_reason_message = "⚠️ None of the generated images met the passing grade (all < 70/100)."

        if not perform_retry and self.grading_enabled and (critic_grade is not None or final_art_grade_for_overall_calc is not None):
            if overall_grade < 70:
                perform_retry = True
                retry_reason_message = f"⚠️ Overall grade ({overall_grade}/100) is below 70."

        if self.grading_enabled and (critic_grade is not None or final_art_grade_for_overall_calc is not None):
            yield {"type": "system", "content": f"📊 Overall Grade: {overall_grade}/100 (Code: {critic_grade or 'N/A'}, Art: {art_grade_display})"}

        if perform_retry and self.current_attempt < self.max_retry_attempts:
            yield {"type": "system", "content": f"{retry_reason_message} Requesting Main Coder to improve... (Attempt {self.current_attempt + 1}/{self.max_retry_attempts})"}
            art_critique_summary_for_retry = "No specific art critiques available for this attempt.\n"
            if all_art_critiques:
                art_critique_summary_for_retry = "Summary of Art Critiques (focus on best image if applicable):\n"
                # ... (rest of art_critique_summary_for_retry logic remains the same)
                if best_image_details:
                    art_critique_summary_for_retry += (f"Best Image ({os.path.basename(best_image_details['image_path'])}, "
                                                       f"Grade: {best_image_details['grade'] or 'N/A'}):\n"
                                                       f"{best_image_details['critique_text'][:400]}...\n\n")
                other_failing_critiques = [c for c in all_art_critiques if c.get('grade', 0) < 70 and c != best_image_details]
                if other_failing_critiques:
                    art_critique_summary_for_retry += "Other critiques for images needing improvement:\n"
                    for c_item in other_failing_critiques[:2]:
                        art_critique_summary_for_retry += f"- {os.path.basename(c_item['image_path'])} (Grade: {c_item['grade']}): {c_item['critique_text'][:200]}...\n"
                elif len(all_art_critiques) > 1 and best_image_details and best_image_details.get('grade', 0) >=70 :
                     art_critique_summary_for_retry += "The best image was acceptable, but other aspects of the request or code may need improvement if overall grade is low.\n"
                elif not best_image_details and all_art_critiques:
                    art_critique_summary_for_retry = "Multiple art critiques provided. Please review them in the chat history.\n"

            retry_intro = (f"RETRY (Original User Prompt: '{original_user_prompt}'):\n\n"
                           f"PREVIOUS ATTEMPT FEEDBACK:\n"
                           f"Code Critic Grade: {critic_grade or 'N/A'}\n"
                           f"Art Critic Best Image Grade: {art_grade_display}\n"
                           f"Overall Grade: {overall_grade}/100\n"
                           f"{retry_reason_message}\n\n"
                           f"Please improve the implementation based on the critique feedback above. "
                           f"Focus on addressing issues in both code and image generation (if applicable).\n\n"
                           f"Art Critiques Summary:\n{art_critique_summary_for_retry.strip()}")
            current_main_coder_prompt_ref_for_retry[0] = f"{retry_intro}\n\n{current_main_coder_prompt_ref_for_retry[0]}" # Modify the passed list's element
            return True # Indicate retry

        elif perform_retry: # Max attempts reached
            yield {"type": "system", "content": f"⚠️ Maximum attempts reached. {retry_reason_message} Final overall grade: {overall_grade}/100"}
        elif self.grading_enabled and (critic_grade is not None or final_art_grade_for_overall_calc is not None) and overall_grade >= 70:
            yield {"type": "system", "content": f"✅ Grade acceptable ({overall_grade}/100). Implementation approved!"}
        elif not self.grading_enabled:
            yield {"type": "system", "content": "✅ Processing complete (grading disabled)."}
            for agent_status_msg_type in ["prompt_enhancer", "art_critic_proactive", "main_coder", "code_critic", "art_critic"]:
                yield {"type": "agent_status_update", "agent": agent_status_msg_type, "status": "inactive"}

        # --- Loser Image Handling ---
        paths_to_trash_this_attempt = []
        if generated_image_paths_batch:
            best_image_path_final = best_image_details.get('image_path') if best_image_details else None
            best_image_grade_final = best_image_details.get('grade', -1) if best_image_details else -1
            if perform_retry:
                paths_to_trash_this_attempt.extend(generated_image_paths_batch)
                yield {"type": "system", "content": f"🗑️ Discarding all {len(generated_image_paths_batch)} images from this attempt due to retry."}
            else:
                if best_image_path_final and best_image_grade_final >= 70:
                    for img_path in generated_image_paths_batch:
                        if img_path != best_image_path_final:
                            paths_to_trash_this_attempt.append(img_path)
                    if paths_to_trash_this_attempt:
                        yield {"type": "system", "content": f"🗑️ Keeping best image '{os.path.basename(best_image_path_final)}'. Trashing {len(paths_to_trash_this_attempt)} other variants."}
                else:
                    paths_to_trash_this_attempt.extend(generated_image_paths_batch)
                    if generated_image_paths_batch:
                        yield {"type": "system", "content": f"🗑️ No single best image met criteria on final attempt. Trashing all {len(generated_image_paths_batch)} generated images."}

        if paths_to_trash_this_attempt:
            unique_paths_to_trash = list(set(paths_to_trash_this_attempt))
            if unique_paths_to_trash:
                trash_path_display = Path(VM_DIR) / TRASH_DIR_NAME
                yield {"type": "system", "content": f"ℹ️ Moving {len(unique_paths_to_trash)} non-selected/failed image(s) to the '{trash_path_display}' folder..."}
                for log_msg in self._move_to_trash(unique_paths_to_trash):
                    yield {"type": "system", "content": log_msg}

        # Phase 4: Collaborative Refinement
        should_use_critic = self._should_invoke_code_critic(original_user_prompt, main_response_text, implementation_results) # Re-check based on original conditions
        should_use_art_critic = self._should_invoke_art_critic(original_user_prompt, main_response_text, implementation_results) # Re-check
        if (should_use_critic or should_use_art_critic) and self._needs_refinement(implementation_results):
            yield {"type": "system", "content": "🔄 Agents collaborating on final refinements..."}
            refinement_suggestions = self._get_collaborative_refinement()
            if refinement_suggestions:
                yield {"type": "agent", "agent": "🤝 Collaborative", "content": refinement_suggestions}

        yield {"type": "system", "content": "✅ Multi-agent analysis complete!"}
        for agent_status_msg_type in ["prompt_enhancer", "art_critic_proactive", "main_coder", "code_critic", "art_critic"]:
             yield {"type": "agent_status_update", "agent": agent_status_msg_type, "status": "inactive"}
        return False # Indicate no retry

    def run_enhanced_interaction(self, original_user_prompt):
        """Enhanced multi-agent interaction with grading and retry system"""
        if not self.client:
            yield {"type": "error", "content": "AI system not configured. Please set API key."}
            return

        # Initial prompt enhancement
        enhanced_user_prompt = yield from self._handle_prompt_enhancement(original_user_prompt)

        # Proactive art guidance
        proactive_art_advice = yield from self._handle_proactive_art_guidance(enhanced_user_prompt)

        current_main_coder_prompt = enhanced_user_prompt
        self.current_attempt = 0
        
        while self.current_attempt < self.max_retry_attempts:
            self.current_attempt += 1
            attempt_suffix = f" (Attempt {self.current_attempt}/{self.max_retry_attempts})" if self.current_attempt > 1 else ""
            
            self._update_project_context()
            
            try:
                # Main Coder Phase
                main_response_text, implementation_results, generated_image_paths_batch = yield from self._execute_main_coder_phase(
                    current_main_coder_prompt, proactive_art_advice, attempt_suffix
                )

                # Critic Evaluations
                critic_grade, all_art_critiques, best_image_details, final_art_grade_for_overall_calc = yield from self._perform_critic_evaluations(
                    original_user_prompt, main_response_text, implementation_results, generated_image_paths_batch
                )
                
                # Retry Logic and Finalization
                # Pass current_main_coder_prompt as a list to allow modification for retry
                current_main_coder_prompt_list_for_retry = [enhanced_user_prompt] # Use enhanced_user_prompt for subsequent retries, not the already modified one.
                
                should_retry = yield from self._handle_retry_and_finalization(
                    original_user_prompt, current_main_coder_prompt_list_for_retry,
                    critic_grade, all_art_critiques, best_image_details,
                    final_art_grade_for_overall_calc, generated_image_paths_batch,
                    main_response_text, implementation_results # Pass these for re-evaluation if needed by _handle_retry_and_finalization
                )
                current_main_coder_prompt = current_main_coder_prompt_list_for_retry[0]


                if should_retry:
                    continue
                else:
                    break # Successful completion or max retries reached without explicit success

            except Exception as e:
                error_msg = f"Enhanced Agent System Error: {e}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": error_msg}
                for agent_status_msg_type in ["prompt_enhancer", "art_critic_proactive", "main_coder", "code_critic", "art_critic"]:
                    yield {"type": "agent_status_update", "agent": agent_status_msg_type, "status": "inactive"}
                break

    def _get_code_critique(self, user_prompt, main_response, implementation_results):
        """Get enhanced code critique"""
        critique_context = f"""
ORIGINAL REQUEST: {user_prompt}

MAIN CODER IMPLEMENTATION: {main_response}

IMPLEMENTATION RESULTS: {self._format_results(implementation_results)}

PROJECT CONTEXT: {self._get_project_summary()}

Please provide a comprehensive code review focusing on quality, security, performance, and best practices.
"""
        
        try:
            response_stream = self.client.models.generate_content_stream(
                model=TEXT_MODEL_NAME,
                contents=[{"text": f"{CRITIC_AGENT_PROMPT}\n\n{critique_context}"}]
            )
            for chunk in response_stream:
                yield chunk.text
        except Exception as e:
            self.error_context.append(f"Code Critic Error: {e}")
            yield f"Error generating code critique: {e}" # Yield error message as part of the stream

    def _get_art_critique(self, user_prompt, main_response, implementation_results, target_image_path=None):
        """Get enhanced art critique with vision capabilities, focusing on a target image if provided."""
        critique_focus_text = ""
        if target_image_path:
            # Make target_image_path relative to VM_DIR for display in the prompt if it's not already
            try:
                rel_target_image_path = Path(target_image_path).relative_to(VM_DIR)
            except ValueError:
                rel_target_image_path = target_image_path # Keep as is if not relative to VM_DIR

            critique_focus_text = f"""
YOU ARE CRITIQUING THIS SPECIFIC IMAGE: {rel_target_image_path}

Please analyze THIS SPECIFIC IMAGE ({rel_target_image_path}) for visual elements, design guidance, and suggest improvements.
All other images in the VISUAL CONTEXT section below are for reference or comparison if needed.
"""

        art_context_text = f"""
ORIGINAL REQUEST: {user_prompt}

MAIN CODER IMPLEMENTATION (may include multiple image generation commands):
{main_response}

IMPLEMENTATION RESULTS (shows files created, including possibly multiple images):
{self._format_results(implementation_results)}
{critique_focus_text}
Please analyze visual elements, provide design guidance, and suggest improvements for better aesthetics and user experience.
"""
        art_context_parts = self._build_visual_context(art_context_text, ART_AGENT_PROMPT)
        
        try:
            response_stream = self.client.models.generate_content_stream(
                model=TEXT_MODEL_NAME,
                contents=art_context_parts
            )
            for chunk in response_stream:
                yield chunk.text
        except Exception as e:
            self.error_context.append(f"Art Critic Error: {e}")
            yield f"Error generating art critique: {e}" # Yield error message as part of the stream

    def _get_proactive_art_guidance(self, current_user_prompt):
        """Get proactive art guidance before image generation."""
        try:
            # Prepare the prompt for the Art Critic
            # The context_text here is primarily the user's request for the new image.
            context_text = f"USER REQUEST FOR NEW IMAGE:\n{current_user_prompt}"

            # Use _build_visual_context to also provide existing images for context.
            # The system_prompt for _build_visual_context will be the PROACTIVE_ART_AGENT_PROMPT
            # with the user request placeholder filled.
            formatted_proactive_prompt = PROACTIVE_ART_AGENT_PROMPT.replace("{{USER_REQUEST}}", current_user_prompt)

            proactive_art_context_parts = self._build_visual_context(
                context_text=context_text, # This provides the user request within the visual context section
                system_prompt=formatted_proactive_prompt # This is the main system prompt for the agent
            )

            response_stream = self.client.models.generate_content_stream(
                model=TEXT_MODEL_NAME,
                contents=proactive_art_context_parts
            )
            full_response_text = ""
            for chunk in response_stream:
                if chunk.text:
                    full_response_text += chunk.text
                    yield chunk.text
            self._log_interaction("proactive_art_critic", full_response_text) # Log the complete text after streaming
            # Note: The return of the accumulated text is handled by the loop yielding chunks.
            # If no chunks, nothing is yielded beyond what the calling function handles.
        except Exception as e:
            self.error_context.append(f"Proactive Art Critic Error: {e}")
            yield f"Error generating proactive art guidance: {e}" # Yield error message as part of the stream


    def _move_to_trash(self, image_paths_to_move):
        """Moves specified image paths to the .trash directory within VM_DIR."""
        messages = []
        # Ensure TRASH_DIR_NAME is defined, e.g. as a global or class constant if not already.
        # For this implementation, assuming TRASH_DIR_NAME is accessible.
        # The trash directory should be inside VM_DIR.
        trash_dir = VM_DIR / TRASH_DIR_NAME
        try:
            trash_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messages.append(f"❌ Error creating trash directory {trash_dir}: {e}")
            return messages # Cannot proceed if trash dir creation fails

        for img_path_str in image_paths_to_move:
            try:
                source_path = Path(img_path_str) # This path is already relative to project root, e.g. "vm/image.png"

                # We need to ensure source_path is interpreted correctly if it's not absolute
                # If img_path_str is like "vm/image.png", Path(img_path_str) is correct.
                # If it could be just "image.png" (expecting it inside VM_DIR), then source_path = VM_DIR / img_path_str
                # Given current usage, img_path_str is 'vm/generated_img.png'

                if not source_path.is_absolute() and not str(source_path).startswith(str(VM_DIR)):
                     # This case should ideally not happen if paths are consistently from generated_image_paths_batch
                    source_path = VM_DIR / source_path.name


                dest_path = trash_dir / source_path.name

                if source_path.exists() and source_path.is_file():
                    try:
                        shutil.move(str(source_path), str(dest_path))
                        messages.append(f"🗑️ Moved '{source_path.name}' to '{TRASH_DIR_NAME}/'.")
                    except Exception as e:
                        messages.append(f"❌ Error moving '{source_path.name}' to trash: {e}")
                elif not source_path.exists():
                    messages.append(f"ℹ️ File not found, cannot trash: '{img_path_str}' (expected at {source_path}).")
                elif not source_path.is_file():
                    messages.append(f"ℹ️ Path is not a file, cannot trash: '{img_path_str}'.")
            except Exception as e: # Catch any error related to path processing for a single file
                messages.append(f"❌ Unexpected error processing path '{img_path_str}' for trashing: {e}")

        return messages

    def _get_collaborative_refinement(self):
        """Get collaborative refinement suggestions"""
        if len(self.conversation_history) < 3:
            return None
            
        refinement_context = f"""
Based on the recent multi-agent analysis, provide collaborative refinement suggestions that combine:
1. Technical implementation improvements
2. Code quality enhancements  
3. Visual and UX improvements

Recent conversation:
{self._get_recent_conversation_summary()}

Focus on actionable improvements that leverage all three agent perspectives.
"""
        
        try:
            response = self.client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=[{"text": refinement_context}]
            )
            return response.text
        except Exception as e:
            return None

    def _update_project_context(self):
        """Update project context for better agent awareness"""
        self.project_context = {
            "files": self._get_project_files(),
            "images": self._get_project_images(),
            "recent_changes": self._get_recent_changes()
        }

    def _build_enhanced_prompt(self, user_prompt, system_prompt, proactive_art_advice=None):
        """Build enhanced prompt with comprehensive context"""
        # Placeholder for integrating proactive_art_advice into the prompt
        # For now, it's just accepted as a parameter.
        # In a future step, this method will be modified to use proactive_art_advice.
        prompt_parts = [{"text": f"{system_prompt}\n\n**PROJECT STATUS:**\n"}]
        if proactive_art_advice:
            prompt_parts.append({"text": f"\n**PROACTIVE ART GUIDANCE:**\n{proactive_art_advice}\n"})

        # Add current files with content
        if VM_DIR.exists():
            for root, dirs, files in os.walk(VM_DIR):
                # Remove TRASH_DIR_NAME from dirs to prevent traversing it
                if TRASH_DIR_NAME in dirs:
                    dirs.remove(TRASH_DIR_NAME)

                for name in sorted(files):
                    rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                    file_path = os.path.join(root, name)
                    
                    try:
                        if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                            try:
                                img = Image.open(file_path)
                                prompt_parts.append({"text": f"\n--- IMAGE: {rel_path} ---\n"})
                                prompt_parts.append(img)
                            except Exception:
                                prompt_parts.append({"text": f"\n--- IMAGE ERROR: {rel_path} ---\n"})
                        else:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read(3000)  # Increased content limit
                            prompt_parts.append({"text": f"\n--- FILE: {rel_path} ---\n{content}\n"})
                    except IOError:
                        continue

        # Add conversation history for context
        if self.conversation_history:
            prompt_parts.append({"text": "\n**CONVERSATION HISTORY:**\n"})
            for entry in self.conversation_history[-8:]:  # More history
                role = entry["role"].replace("_", " ").title()
                content = entry["content"][:300] + "..." if len(entry["content"]) > 300 else entry["content"]
                prompt_parts.append({"text": f"{role}: {content}\n\n"})

        # Add error context if any
        if self.error_context:
            prompt_parts.append({"text": f"\n**RECENT ERRORS:**\n{chr(10).join(self.error_context[-3:])}\n"})

        prompt_parts.append({"text": f"\n**USER REQUEST:**\n{user_prompt}"})
        return prompt_parts

    def _build_visual_context(self, context_text, system_prompt):
        """Build visual context for art critic with all images"""
        context_parts = [{"text": f"{system_prompt}\n\n{context_text}\n\n**VISUAL CONTEXT:**\n"}]
        
        if VM_DIR.exists():
            image_count = 0
            for root, dirs, files in os.walk(VM_DIR):
                # Remove TRASH_DIR_NAME from dirs to prevent traversing it
                if TRASH_DIR_NAME in dirs:
                    dirs.remove(TRASH_DIR_NAME)

                for name in files:
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        file_path = os.path.join(root, name)
                        rel_path = os.path.relpath(file_path, VM_DIR)
                        try:
                            img = Image.open(file_path)
                            context_parts.append({"text": f"\n--- ANALYZING IMAGE: {rel_path} ---\n"})
                            context_parts.append(img)
                            image_count += 1
                        except Exception:
                            continue
            
            if image_count == 0:
                context_parts.append({"text": "No images found in project.\n"})
        
        return context_parts

    def _should_invoke_code_critic(self, user_prompt, main_response, implementation_results):
        """Smart detection for when Code Critic is actually needed"""
        # Skip for simple operational commands
        simple_commands = [
            'run', 'start', 'execute', 'launch', 'install', 'update', 'pip install',
            'npm install', 'serve', 'host', 'deploy', 'build', 'compile'
        ]
        prompt_lower = user_prompt.lower()
        if any(cmd in prompt_lower and len(prompt_lower.split()) <= 4 for cmd in simple_commands):
            return False
        
        # Only invoke if there's substantial code creation/modification
        code_creation_indicators = [
            'create_file', 'write_to_file', 'function', 'class', 'algorithm',
            'implement', 'refactor', 'optimize', 'fix bug', 'debug', 'security',
            'performance', 'review code', 'analyze code'
        ]
        
        text_to_check = f"{user_prompt} {main_response}".lower()
        has_code_work = any(indicator in text_to_check for indicator in code_creation_indicators)
        
        # Also check if significant code was actually created/modified
        has_file_changes = any(result.get("type") == "system" and 
                              any(op in result.get("content", "") for op in ["Created file", "Updated file"])
                              for result in implementation_results)
        
        return has_code_work and has_file_changes

    def _should_invoke_art_critic(self, user_prompt, main_response, implementation_results, mode="reactive"):
        """Smart detection for when Art Critic is actually needed, with proactive/reactive modes."""
        prompt_lower = user_prompt.lower()

        if mode == "proactive":
            proactive_visual_keywords = [
                'generate image', 'create image', 'make image', 'draw image',
                'generate logo', 'create logo', 'design logo',
                'generate banner', 'create banner', 'design banner',
                'generate icon', 'create icon', 'design icon',
                'generate picture', 'create picture',
                'new art for', 'visual asset for', 'generate art for'
            ]
            if any(keyword in prompt_lower for keyword in proactive_visual_keywords):
                return True
            return False

        # Reactive mode (default)
        # Skip for simple operational commands if not explicitly about visuals
        simple_commands = [
            'run', 'start', 'execute', 'launch', 'install', 'update', 'serve'
        ]
        # Check for explicit visual analysis first, as this should always trigger reactive
        explicit_visual_analysis = any(phrase in prompt_lower for phrase in [
            'analyze image', 'review design', 'visual feedback', 'art critique',
            'design review', 'improve visuals'
        ])
        if explicit_visual_analysis:
            return True

        # If not explicit analysis, then check if it's a simple command that isn't visual
        if any(cmd in prompt_lower and len(prompt_lower.split()) <= 4 for cmd in simple_commands):
            # Check if even simple commands might be visual (e.g. "run image generation")
            # This is a bit broad, but tries to catch simple visual commands.
            if not any(vis_cmd in prompt_lower for vis_cmd in ['image', 'visual', 'art', 'design', 'graphic']):
                return False # It's a simple, non-visual command

        # Broader visual work indicators for reactive mode
        visual_work_indicators = [
            'generate_image', 'create image', 'design', 'visual', 'ui', 'interface',
            'color', 'layout', 'style', 'aesthetic', 'art', 'graphic', 'icon',
            'logo', 'banner', 'picture', 'photo'
            # 'analyze image', 'review design' etc. are covered by explicit_visual_analysis now
        ]
        
        text_to_check = f"{user_prompt} {main_response}".lower() # main_response can be empty for proactive
        has_visual_work = any(indicator in text_to_check for indicator in visual_work_indicators)
        
        # Check if images were actually generated/modified (only relevant for reactive)
        has_image_changes = any(result.get("type") == "file_changed" and 
                               result.get("content", "").lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
                               for result in implementation_results)
        
        return has_visual_work or has_image_changes # explicit_visual_analysis already returned True if matched

    def _needs_refinement(self, implementation_results):
        """Determine if refinement is needed based on results"""
        error_count = sum(1 for result in implementation_results if result.get("type") == "error")
        # Only suggest refinement if there are actual errors or complex operations
        complex_operations = sum(1 for result in implementation_results 
                               if result.get("type") == "system" and 
                               any(op in result.get("content", "") for op in ["Created file", "Updated file", "Generated"]))
        
        return error_count > 0 or complex_operations > 2

    def _has_project_images(self):
        """Check if project contains images"""
        if not VM_DIR.exists():
            return False
        
        for root, _, files in os.walk(VM_DIR):
            for name in files:
                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    return True
        return False

    def _process_enhanced_commands(self, response_text):
        """Enhanced command processing with a more specific regex, pre-checks, and detailed error logging."""
        # Regex to find function-like calls: command_name(arguments)
        # It looks for a valid identifier, followed by '(', any characters (non-greedy), and then ')'
        # Allows for optional whitespace around the command itself within the backticks.
        command_pattern = re.compile(r'`\s*([a-zA-Z_][\w\.]*\s*\(.*?\))\s*`', re.DOTALL)
        matches = command_pattern.finditer(response_text)

        for match in matches:
            command_str = match.group(1).strip() # command_str is now the pure command like "create_file(...)"

            if not command_str:
                continue

            # Pre-check if the command string starts with a known command handler name followed by an opening parenthesis
            # This helps filter out malformed or unintended matches before attempting ast.parse
            if not any(command_str.startswith(known_cmd + "(") for known_cmd in self.command_handlers.keys()):
                # Optionally log this as a skipped potential command if debugging is needed
                # self.error_context.append(f"Skipped potential command (unknown prefix): '{command_str[:50]}...'")
                yield {"type": "system", "content": f"ℹ️ Note: Ignoring potential command-like text: `{command_str[:100]}{'...' if len(command_str) > 100 else ''}`"}
                continue

            try:
                # Attempt to parse the command string as a Python expression (specifically, a function call)
                parsed_expr = ast.parse(command_str, mode="eval")
                call_node = parsed_expr.body
                
                # Ensure it's a Call node (function call)
                if not isinstance(call_node, ast.Call):
                    # This should ideally be caught by the regex, but as a safeguard:
                    self.error_context.append(f"Command parsing error: Not a function call - '{command_str}'")
                    yield {"type": "error", "content": f"❌ Command error: Not a function call - `{command_str}`"}
                    continue

                func_name = call_node.func.id
                if func_name not in self.command_handlers:
                    self.error_context.append(f"Unknown command: '{func_name}' in '{command_str}'")
                    yield {"type": "error", "content": f"❌ Unknown command: `{func_name}`"}
                    continue

                # Safely evaluate arguments
                args = []
                for arg_node in call_node.args:
                    try:
                        args.append(ast.literal_eval(arg_node))
                    except ValueError as ve:
                        # Handle cases where an argument is not a simple literal (e.g., a variable or complex expression)
                        # For now, we'll log and skip this command as it's not supported by literal_eval
                        error_msg = f"Command argument error: Non-literal argument in '{command_str}'. Argument: {ast.dump(arg_node)}. Error: {ve}"
                        self.error_context.append(error_msg)
                        yield {"type": "error", "content": f"❌ Command error: Invalid argument in `{command_str}`"}
                        break  # Break from processing args for this command
                else: # This 'else' belongs to the for loop, executed if the loop completed without a 'break'
                    result = self.command_handlers[func_name](*args)

                    if func_name == "generate_image":
                        for update in result: # generate_image is a generator
                            yield update
                    else:
                        yield {"type": "system", "content": result}

                    # Track successful changes
                    if func_name in ["create_file", "write_to_file", "generate_image"]:
                        self.project_context["recent_changes"].append({
                            "command": func_name,
                            "args": args, # Log sanitized args
                            "timestamp": time.time()
                        })
                    continue # Move to the next matched command

                # If the for loop for args was broken (due to bad arg), skip to next command match
                if args and isinstance(args[-1], Exception): # Check if loop was broken by an error
                     continue


            except SyntaxError as se:
                error_msg = f"Command syntax error: Unable to parse '{command_str}'. Error: {se}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": f"❌ Command syntax error: `{command_str}`"}
            except ValueError as ve: # Catches errors from ast.literal_eval if the whole command_str was somehow evaluated
                error_msg = f"Command value error: Problem with argument values in '{command_str}'. Error: {ve}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": f"❌ Command value error: `{command_str}`"}
            except Exception as e: # General catch-all for other unexpected errors
                error_msg = f"Unexpected command execution error for '{command_str}'. Error: {type(e).__name__} - {e}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": f"❌ Unexpected error processing command: `{command_str}`"}

    def _log_interaction(self, role, content):
        """Logs an interaction to the conversation history, maintaining a manageable length."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        
        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-15:]

    def _format_results(self, results):
        """Formats a list of implementation results for inclusion in agent prompts."""
        if not results:
            return "No implementation results"
        
        formatted = []
        for result in results[-5:]:  # Last 5 results
            formatted.append(f"- {result.get('type', 'unknown')}: {result.get('content', '')}")
        return "\n".join(formatted)

    def _get_project_summary(self):
        """Gets a concise summary of the current project state (file counts)."""
        file_count = len(self.project_context.get("files", []))
        image_count = len(self.project_context.get("images", []))
        recent_changes = len(self.project_context.get("recent_changes", []))
        
        return f"Files: {file_count}, Images: {image_count}, Recent changes: {recent_changes}"

    def _get_recent_conversation_summary(self):
        """Gets a summary of the most recent part of the conversation history."""
        if not self.conversation_history:
            return "No recent conversation"
        
        recent = self.conversation_history[-6:]
        summary = []
        for entry in recent:
            role = entry["role"].replace("_", " ").title()
            content = entry["content"][:150] + "..." if len(entry["content"]) > 150 else entry["content"]
            summary.append(f"{role}: {content}")
        
        return "\n".join(summary)

    def _get_project_files(self):
        """Get list of project files"""
        files = []
        if VM_DIR.exists():
            for root, _, filenames in os.walk(VM_DIR):
                for name in filenames:
                    if not name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                        files.append(rel_path)
        return files

    def _get_project_images(self):
        """Get list of project images"""
        images = []
        if VM_DIR.exists():
            for root, _, filenames in os.walk(VM_DIR):
                for name in filenames:
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                        images.append(rel_path)
        return images

    def _get_recent_changes(self):
        """Get recent project changes"""
        return self.project_context.get("recent_changes", [])[-10:]  # Last 10 changes

    def _extract_grade(self, agent_response):
        """Extract numerical grade from agent response"""
        if not agent_response:
            return None
            
        # Look for "GRADE: XX/100" pattern
        grade_match = re.search(r'GRADE:\s*(\d+)/100', agent_response, re.IGNORECASE)
        if grade_match:
            return int(grade_match.group(1))
        
        # Fallback: look for standalone numbers near "grade"
        # Prefer 1-3 digits, whole word matching for "grade" and the number
        grade_match = re.search(r'\bgrade[:\s]*(\d{1,3})\b', agent_response, re.IGNORECASE)
        if grade_match:
            return int(grade_match.group(1))
            
        return None

    def _calculate_overall_grade(self, critic_grade, art_grade):
        """Calculate overall grade from individual agent grades"""
        grades = [g for g in [critic_grade, art_grade] if g is not None]
        if not grades:
            return 85  # Default grade if no grading available
        return sum(grades) // len(grades)  # Average of available grades

    def _safe_path(self, filename):
        """Sanitize file paths to ensure they are within VM_DIR and prevent traversal."""
        if not filename: # Disallow empty filenames
            return None

        # Prevent absolute paths in the provided filename argument
        if Path(filename).is_absolute():
            return None

        # Combine with VM_DIR and then normalize
        # os.path.abspath will normalize the path (e.g., remove '..') and make it absolute.
        # This helps in comparing it reliably against the VM_DIR's absolute path.
        # It's crucial that VM_DIR is an absolute path for this comparison or that both are treated consistently.
        # Since VM_DIR is Path('vm'), it's relative to the execution directory.

        abs_vm_dir = os.path.abspath(VM_DIR)

        # Construct the full path
        full_path = VM_DIR / filename
        abs_full_path = os.path.abspath(full_path)

        # Check if the normalized full path starts with the normalized VM_DIR path
        if os.path.commonprefix([abs_full_path, abs_vm_dir]) != abs_vm_dir:
            return None # Path is outside VM_DIR or filename tries to escape

        # Additionally, ensure that the resolved path doesn't escape via symlinks
        # This is harder to do perfectly without actually resolving, which might fail for create_file.
        # The commonprefix check on abspath is a good primary defense.
        # For now, we rely on the abspath check. A more advanced check might involve Path.resolve()
        # but would need careful handling if the path doesn't exist yet.

        return full_path # Return the Path object, still relative to execution if VM_DIR is

    def _create_file(self, path, content=""):
        """Create new file with enhanced error handling"""
        filepath = self._safe_path(path)
        if not filepath:
            return f"❌ Invalid path: {path}"

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding='utf-8')
            return f"✅ Created file: {path} ({len(content)} characters)"
        except Exception as e:
            error_msg = f"❌ Error creating file {path}: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def _write_to_file(self, path, content):
        """Write to file with enhanced feedback"""
        filepath = self._safe_path(path)
        if not filepath:
            return f"❌ Invalid path: {path}"
        
        if not filepath.exists():
            return f"❌ File not found: {path}"

        try:
            old_size = filepath.stat().st_size if filepath.exists() else 0
            filepath.write_text(content, encoding='utf-8')
            new_size = len(content.encode('utf-8'))
            return f"✅ Updated file: {path} ({old_size} → {new_size} bytes)"
        except Exception as e:
            error_msg = f"❌ Error writing to file {path}: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def _delete_file(self, path):
        """Delete file with enhanced feedback"""
        filepath = self._safe_path(path)
        if not filepath or not filepath.exists():
            return f"❌ File not found: {path}"

        try:
            if filepath.is_dir():
                # Use shutil.rmtree for robust recursive directory deletion
                shutil.rmtree(filepath)
                return f"✅ Deleted directory: {path}"
            else:
                file_size = filepath.stat().st_size
                filepath.unlink()
                return f"✅ Deleted file: {path} ({file_size} bytes)"
        except Exception as e:
            error_msg = f"❌ Error deleting {path}: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def _run_command(self, command):
        """Execute shell command with enhanced output"""
        if not command:
            return "❌ No command provided"

        try:
            start_time = time.time()
            # SECURITY CRITICAL: shell=True is dangerous with untrusted input.
            # Use shell=False and split the command using shlex for safety.
            import shlex
            cmd_parts = shlex.split(command)
            if not cmd_parts: # Handle empty command after shlex split
                return "❌ Empty command provided"

            proc = subprocess.run(
                cmd_parts, # Pass as a list
                cwd=VM_DIR,
                shell=False, # Set to False for security
                capture_output=True,
                text=True,
                timeout=120  # Increased timeout
            )
            execution_time = time.time() - start_time
            
            output = f"🔧 Command: {command}\n⏱️ Execution time: {execution_time:.2f}s\n"
            
            if proc.stdout:
                output += f"📤 STDOUT:\n{proc.stdout}\n"
            if proc.stderr:
                output += f"⚠️ STDERR:\n{proc.stderr}\n"
                self.error_context.append(f"Command stderr: {proc.stderr}")
            
            if proc.returncode == 0:
                output += "✅ Command completed successfully"
            else:
                output += f"❌ Command failed with exit code: {proc.returncode}"
                
            return output
            
        except subprocess.TimeoutExpired:
            error_msg = "⏰ Command timed out after 120 seconds"
            self.error_context.append(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Command execution error: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def generate_image(self, path, prompt):
        """Enhanced image generation with better feedback"""
        if not self.client:
            yield {"type": "error", "content": "❌ Image generation not configured"}
            return

        filepath = self._safe_path(path)
        if not filepath:
            yield {"type": "error", "content": f"❌ Invalid path: {path}"}
            return

        yield {"type": "system", "content": f"🎨 Generating image: {path}"}
        yield {"type": "system", "content": f"📝 Prompt: {prompt}"}

        try:
            config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            response = self.client.models.generate_content(
                model=IMAGE_MODEL_NAME,
                contents=prompt,
                config=config
            )

            image_bytes = None
            candidates = getattr(response, "candidates", [])
            if candidates:
                parts = candidates[0].content.parts
                for part in parts:
                    if hasattr(part, "inline_data") and part.inline_data is not None:
                        image_bytes = part.inline_data.data
                        break

            if not image_bytes:
                yield {"type": "error", "content": "❌ No image data received from AI"}
                return

            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(image_bytes)
            
            # Get image info
            try:
                img = Image.open(filepath)
                width, height = img.size
                file_size = filepath.stat().st_size
                yield {"type": "system", "content": f"✅ Image generated: {width}x{height}px, {file_size} bytes"}
            except Exception:
                yield {"type": "system", "content": f"✅ Image generated: {path}"}
            
            yield {"type": "file_changed", "content": str(filepath)}

        except Exception as e:
            error_msg = f"❌ Image generation failed: {e}"
            self.error_context.append(error_msg)
            yield {"type": "error", "content": error_msg}

# -----------------------------------------------------------------------------
# Enhanced IDE Application
# -----------------------------------------------------------------------------
class EnhancedGeminiIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1600x1000")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Dark Theme Colors ---
        self.bg_color_dark = "#2E2E2E"    # Dark gray for main backgrounds
        self.fg_color_light = "#F0F0F0"   # Light gray/white for text
        self.bg_color_medium = "#3C3C3C"  # A slightly lighter dark shade
        self.border_color = "#505050"     # A color for borders
        self.accent_color = "#007ACC"     # Accent color for selections/highlights

        # Chat-specific colors
        self.user_chat_color = "#7FFFD4"      # Aquamarine
        self.system_chat_color = "#4DB6AC"    # Tealish (a bit desaturated cyan/green)
        self.timestamp_chat_color = "#B0B0B0" # Lighter Gray for timestamps
        self.error_chat_color = "#FF8A80"     # Softer Red for errors in chat (was #ff0000)

        # Agent status indicator colors
        self.agent_status_inactive_color = "#66BB6A" # Medium Green
        self.agent_status_active_color = "#FFA726"   # Amber/Orange
        self.agent_status_error_color = "#EF5350"    # Soft Red

        self.style = ttk.Style()
        self.style.theme_use('clam') # Using a theme that allows more customization

        # Main window background
        self.configure(bg=self.bg_color_dark)

        # --- Base ttk Styles ---
        self.style.configure("TFrame", background=self.bg_color_dark)
        self.style.configure(
            "TLabelframe",
            background=self.bg_color_dark,
            bordercolor=self.border_color,
            relief=tk.SOLID, # Added relief for better visibility
            borderwidth=1
        )
        self.style.configure(
            "TLabelframe.Label",
            background=self.bg_color_dark,
            foreground=self.fg_color_light,
            padding=(5, 2) # Add some padding to labelframe labels
        )
        # Add a border to PanedWindow Sash for visibility
        self.style.configure("TPanedwindow", background=self.bg_color_dark) # Main pane background
        self.style.configure("Sash", background=self.bg_color_medium, bordercolor=self.border_color, relief=tk.RAISED, sashthickness=6)

        # Scrollbar Style (for Treeview and any other ttk.Scrollbar)
        self.style.configure("Vertical.TScrollbar", background=self.bg_color_medium, troughcolor=self.bg_color_dark, bordercolor=self.border_color, arrowcolor=self.fg_color_light, relief=tk.FLAT, arrowsize=12)
        self.style.configure("Horizontal.TScrollbar", background=self.bg_color_medium, troughcolor=self.bg_color_dark, bordercolor=self.border_color, arrowcolor=self.fg_color_light, relief=tk.FLAT, arrowsize=12)
        self.style.map("TScrollbar",
            background=[('active', self.accent_color), ('!active', self.bg_color_medium)],
            arrowcolor=[('pressed', self.accent_color), ('!pressed', self.fg_color_light)]
        )

        # Button Style
        self.style.configure("TButton", background=self.accent_color, foreground="white", padding=(8, 4), font=('Segoe UI', 9, 'bold'), borderwidth=1, relief=tk.RAISED, bordercolor=self.accent_color)
        self.style.map("TButton",
                       background=[('active', '#005f9e'), ('pressed', '#004c8c'), ('disabled', self.bg_color_medium)],
                       foreground=[('disabled', self.border_color)],
                       relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)])

        # Treeview Style
        self.style.configure("Treeview", background=self.bg_color_medium, foreground=self.fg_color_light, fieldbackground=self.bg_color_medium, rowheight=22, borderwidth=1, relief=tk.SOLID, bordercolor=self.border_color)
        self.style.map("Treeview",
                       background=[('selected', self.accent_color)],
                       foreground=[('selected', "white")])
        self.style.configure("Treeview.Heading", background=self.bg_color_dark, foreground=self.fg_color_light, relief=tk.FLAT, padding=(5, 5), font=('Segoe UI', 9, 'bold'), borderwidth=0)
        self.style.map("Treeview.Heading",
                       background=[('active', self.bg_color_medium)],
                       relief=[('active', tk.GROOVE), ('!active', tk.FLAT)])

        # Notebook Style
        self.style.configure("TNotebook", background=self.bg_color_dark, tabmargins=(5, 5, 5, 0), borderwidth=1, bordercolor=self.border_color)
        self.style.configure("TNotebook.Tab", background=self.bg_color_medium, foreground=self.fg_color_light, padding=(8,4), font=('Segoe UI', 9), borderwidth=0, relief=tk.FLAT)
        self.style.map("TNotebook.Tab",
                       background=[("selected", self.accent_color), ("active", self.bg_color_dark)],
                       foreground=[("selected", "white"), ("active", self.fg_color_light)],
                       relief=[("selected", tk.FLAT), ("!selected", tk.FLAT)],
                       borderwidth=[("selected",0)])

        # General Label Style (for Enhancer toggle label, status bar agent icons)
        self.style.configure("TLabel", background=self.bg_color_dark, foreground=self.fg_color_light, padding=2)
        # Specific style for status bar text for more control if needed
        self.style.configure("Status.TLabel", background=self.bg_color_dark, foreground=self.fg_color_light, padding=5, relief=tk.FLAT)


        VM_DIR.mkdir(exist_ok=True)
        self.msg_queue = queue.Queue()
        self.current_image = None
        self.current_open_file_path = None

        # Debouncing variables
        self._debounce_refresh_id = None
        self._debounce_insights_id = None
        self._save_timer = None # Ensure _save_timer is initialized
        self._debounce_interval = 300  # milliseconds

        self._create_enhanced_menu()
        self._create_enhanced_layout()
        self._create_enhanced_status_bar()

        api_key = load_api_key()
        if not api_key and GENAI_IMPORTED:
            self.prompt_api_key()
        elif GENAI_IMPORTED:
            self.configure_enhanced_agents(api_key)
        else:
            messagebox.showerror("Missing Dependency", "Install google-genai: pip install google-genai")
            self.status_var.set("❌ google-genai not installed")

        self.after(100, self._process_messages)

    def _create_enhanced_menu(self):
        """Create enhanced application menu"""
        menubar = tk.Menu(self)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📄 New File", command=self.new_file)
        file_menu.add_command(label="💾 Save File", command=self.save_current_file)
        file_menu.add_command(label="🔄 Refresh Files", command=self.refresh_files)
        file_menu.add_separator()
        file_menu.add_command(label="🧹 Clear Chat", command=self.clear_chat)
        file_menu.add_command(label="📊 Project Stats", command=self.show_project_stats)
        menubar.add_cascade(label="File", menu=file_menu)

        # Agents menu
        agents_menu = tk.Menu(menubar, tearoff=0)
        agents_menu.add_command(label="🤖 Test Main Coder", command=lambda: self.test_agent("main"))
        agents_menu.add_command(label="📊 Test Code Critic", command=lambda: self.test_agent("critic"))
        agents_menu.add_command(label="🎨 Test Art Critic", command=lambda: self.test_agent("art"))
        agents_menu.add_separator()
        agents_menu.add_command(label="🔄 Reset Agent Memory", command=self.reset_agent_memory)
        # Prompt Enhancer toggle is now a Canvas switch in the main UI, not a menu item.
        menubar.add_cascade(label="Agents", menu=agents_menu)

        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="🔑 Set API Key", command=self.prompt_api_key)
        settings_menu.add_command(label="⚙️ Agent Settings", command=self.show_agent_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        # Apply basic styling to top-level menubar
        menubar.config(bg=self.bg_color_dark, fg=self.fg_color_light, activebackground=self.accent_color, activeforeground="white", relief=tk.FLAT, borderwidth=0)
        # Style individual menus
        for menu_item in [file_menu, agents_menu, settings_menu]:
            menu_item.config(bg=self.bg_color_medium, fg=self.fg_color_light, activebackground=self.accent_color, activeforeground="white", relief=tk.FLAT, borderwidth=0)

        self.config(menu=menubar)

    def _setup_left_panel(self, parent_pane):
        """Sets up the left panel with image preview and file tree."""
        left_frame = ttk.Frame(parent_pane)
        parent_pane.add(left_frame, weight=1)

        # Enhanced image preview
        img_frame = ttk.LabelFrame(left_frame, text="🖼️ Visual Preview", padding=5)
        img_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.canvas = tk.Canvas(img_frame, bg=self.bg_color_medium, height=320, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(160, 160, text="🖼️ No image selected\nImages will be analyzed by Art Critic",
                               fill=self.fg_color_light, font=("Arial", 11), justify=tk.CENTER)

        # Enhanced file tree
        tree_frame = ttk.LabelFrame(left_frame, text="📁 Project Explorer", padding=5)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("fullpath", "size"), show="tree")
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.column("fullpath", width=0, stretch=False)
        self.tree.column("size", width=80)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self._attach_enhanced_tree_context_menu()
        return left_frame

    def _setup_right_panel(self, parent_pane):
        """Sets up the right panel with the notebook for editor, chat, and insights."""
        right_frame = ttk.Frame(parent_pane)
        parent_pane.add(right_frame, weight=3)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Enhanced editor tab
        editor_frame = ttk.Frame(self.notebook)
        self.editor = scrolledtext.ScrolledText(
            editor_frame, wrap=tk.WORD, font=("Consolas", 12), padx=15, pady=15,
            bg=self.bg_color_medium, fg=self.fg_color_light, insertbackground=self.fg_color_light,
            relief=tk.FLAT, borderwidth=0, highlightthickness=1, highlightbackground=self.border_color
        )
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.frame.config(background=self.bg_color_dark)
        self.notebook.add(editor_frame, text="📝 Code Editor")

        # Enhanced multi-agent chat tab
        chat_frame = ttk.Frame(self.notebook)
        self.chat = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, font=("Segoe UI", 11), padx=15, pady=15, state="disabled",
            bg=self.bg_color_medium, fg=self.fg_color_light, insertbackground=self.fg_color_light,
            relief=tk.FLAT, borderwidth=0, highlightthickness=1, highlightbackground=self.border_color
        )
        self.chat.pack(fill=tk.BOTH, expand=True)
        self.chat.frame.config(background=self.bg_color_dark)
        self.notebook.add(chat_frame, text="🤖 Multi-Agent Chat")

        # Project insights tab
        insights_frame = ttk.Frame(self.notebook)
        self.insights = scrolledtext.ScrolledText(
            insights_frame, wrap=tk.WORD, font=("Segoe UI", 10), padx=15, pady=15, state="disabled",
            bg=self.bg_color_medium, fg=self.fg_color_light, relief=tk.FLAT, borderwidth=0,
            highlightthickness=1, highlightbackground=self.border_color
        )
        self.insights.pack(fill=tk.BOTH, expand=True)
        self.insights.frame.config(background=self.bg_color_dark)
        self.notebook.add(insights_frame, text="📊 Project Insights")
        return right_frame

    def _setup_input_area(self, parent_frame):
        """Sets up the input text area and control buttons."""
        input_frame = ttk.Frame(parent_frame)
        input_frame.pack(fill=tk.X, pady=(0, 5))

        self.input_txt = tk.Text(
            input_frame, height=4, wrap=tk.WORD, font=("Segoe UI", 11), padx=10, pady=10,
            bg=self.bg_color_medium, fg=self.fg_color_light, insertbackground=self.fg_color_light,
            relief=tk.FLAT, borderwidth=1, highlightbackground=self.border_color,
            highlightcolor=self.accent_color, highlightthickness=1
        )
        self.input_txt.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_txt.bind("<Control-Return>", lambda e: self.send_enhanced_prompt())
        self.input_txt.insert("1.0", "💬 Ask the multi-agent system anything... (Ctrl+Enter to send)")
        self.input_txt.bind("<FocusIn>", self._clear_placeholder)
        self.input_txt.bind("<FocusOut>", self._restore_placeholder)

        control_button_frame = ttk.Frame(input_frame)
        control_button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        self.enhancer_toggle_label = ttk.Label(control_button_frame, text="Enhancer:")
        self.enhancer_toggle_label.pack(side=tk.LEFT, padx=(0, 2), anchor='center')

        self.enhancer_toggle_switch = tk.Canvas(
            control_button_frame, width=50, height=22, borderwidth=0, relief=tk.FLAT, cursor="hand2"
        )
        self.enhancer_toggle_switch.pack(side=tk.LEFT, padx=(0, 8), anchor='center')

        self.screenshot_btn = ttk.Button(control_button_frame, text="📸", command=self.upload_screenshot, width=3)
        self.screenshot_btn.pack(side=tk.LEFT, padx=(0, 3), anchor='center')
        
        self.send_btn = ttk.Button(control_button_frame, text="🚀 Send", command=self.send_enhanced_prompt)
        self.send_btn.pack(side=tk.LEFT, anchor='center')
        self.enhancer_toggle_switch.bind("<Button-1>", self._toggle_prompt_enhancer)


    def _create_enhanced_layout(self):
        """Create enhanced UI layout"""
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._setup_left_panel(main_pane)
        right_frame = self._setup_right_panel(main_pane) # right_frame is parent for input_area
        self._setup_input_area(right_frame) # Input area is part of the right_frame, not the notebook

        self.editor.bind("<Control-s>", lambda e: self.save_current_file())
        self._setup_enhanced_syntax_highlighting()
        self.editor.bind("<KeyRelease>", self._on_editor_key_release)
        self._schedule_refresh_files() # Initial refresh

    def _schedule_refresh_files(self):
        """Debounces the refresh_files call."""
        if self._debounce_refresh_id:
            self.after_cancel(self._debounce_refresh_id)
        self._debounce_refresh_id = self.after(self._debounce_interval, self.refresh_files)

    def _schedule_update_insights(self):
        """Debounces the update_agent_insights call."""
        if self._debounce_insights_id:
            self.after_cancel(self._debounce_insights_id)
        self._debounce_insights_id = self.after(self._debounce_interval, self.update_agent_insights)

    def _setup_enhanced_syntax_highlighting(self):
        """Enhanced syntax highlighting"""
        # Dark theme syntax colors
        self.editor.tag_configure("keyword", foreground="#569cd6")
        self.editor.tag_configure("string", foreground="#ce9178")
        self.editor.tag_configure("comment", foreground="#6a9955")
        self.editor.tag_configure("number", foreground="#b5cea8")
        self.editor.tag_configure("function", foreground="#dcdcaa")
        self.editor.tag_configure("class", foreground="#4ec9b0")
        self.editor.tag_configure("operator", foreground="#d4d4d4")

        self.syntax_patterns = {
            "keyword": r"\b(def|class|import|from|for|while|if|elif|else|return|in|and|or|not|is|with|as|try|except|finally|raise|yield|pass|continue|break|global|nonlocal|lambda|assert|async|await)\b",
            "string": r"(\".*?\"|\'.*?\'|\"\"\".*?\"\"\"|\'\'\'.*?\'\'\')",
            "comment": r"#.*",
            "number": r"\b\d+(\.\d*)?\b",
            "function": r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()",
            "class": r"\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            "operator": r"[+\-*/=<>!&|^~%]"
        }

    def _apply_full_syntax_highlighting(self): # Renamed here
        """Apply full syntax highlighting to the entire document."""
        content = self.editor.get("1.0", tk.END)

        for tag in self.syntax_patterns.keys():
            self.editor.tag_remove(tag, "1.0", tk.END)

        for tag, pattern in self.syntax_patterns.items():
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                start, end = match.span()
                self.editor.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

    def _apply_optimized_syntax_highlighting(self, event=None):
        """Apply syntax highlighting only to a range of lines around the edit."""
        try:
            current_pos = self.editor.index(tk.INSERT)
            current_line = int(current_pos.split('.')[0])

            # Define the range of lines to highlight (e.g., 10 lines above and below)
            start_line = max(1, current_line - 10)
            # Ensure end_line does not exceed the document's last line
            last_doc_line_str = self.editor.index(f"{tk.END}-1c").split('.')[0] # Get "line.char" then "line"
            last_doc_line = int(last_doc_line_str) if last_doc_line_str.isdigit() else 1 # Handle empty or non-numeric doc case

            end_line = min(last_doc_line, current_line + 10)

            # Ensure start_line is not greater than end_line, can happen if last_doc_line is small
            if start_line > end_line:
                start_line = end_line

            start_index = f"{start_line}.0"
            end_index = f"{end_line}.end"

            # Get the content for this specific range
            content_to_highlight = self.editor.get(start_index, end_index)
            if not content_to_highlight: # Nothing to do if the range is empty
                return

            # Remove old tags only from this range
            for tag_key in self.syntax_patterns.keys(): # Use a consistent variable name like tag_key or pattern_name
                self.editor.tag_remove(tag_key, start_index, end_index)

            # Apply patterns to the extracted content
            for tag_key, pattern in self.syntax_patterns.items():
                for match in re.finditer(pattern, content_to_highlight, re.MULTILINE | re.DOTALL):
                    match_start_offset, match_end_offset = match.span()

                    # Calculate absolute document indices for the match
                    abs_match_start = self.editor.index(f"{start_index} + {match_start_offset} chars")
                    abs_match_end = self.editor.index(f"{start_index} + {match_end_offset} chars")

                    self.editor.tag_add(tag_key, abs_match_start, abs_match_end)
        except Exception:
            # Optional: log this error, but don't let it crash the app
            # print(f"Error in optimized syntax highlighting: {e}")
            # Fallback to full highlighting in case of error during optimized highlighting
            self._apply_full_syntax_highlighting()
            pass


    def _on_editor_key_release(self, event=None):
        """Enhanced editor key release handler"""
        # Use optimized highlighting for key releases
        self._apply_optimized_syntax_highlighting()

        # Auto-save after 2 seconds of inactivity
        if hasattr(self, '_save_timer'):
            self.after_cancel(self._save_timer)
        self._save_timer = self.after(2000, self._auto_save)

    def _auto_save(self):
        """Auto-save current file if one is open."""
        if self.current_open_file_path:
            self.save_current_file()

    def _clear_placeholder(self, event):
        """Clears the placeholder text from the input field on focus."""
        if self.input_txt.get("1.0", tk.END).strip().startswith("💬 Ask the multi-agent"):
            self.input_txt.delete("1.0", tk.END)

    def _restore_placeholder(self, event):
        """Restores placeholder text to the input field if it's empty on focus out."""
        if not self.input_txt.get("1.0", tk.END).strip():
            self.input_txt.insert("1.0", "💬 Ask the multi-agent system anything... (Ctrl+Enter to send)")

    def _attach_enhanced_tree_context_menu(self):
        """Enhanced context menu for file tree"""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="📝 Rename", command=self.rename_file)
        self.context_menu.add_command(label="🗑️ Delete", command=self.delete_file)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔍 Analyze with Agents", command=self.analyze_selected_file)
        self.context_menu.add_command(label="🎨 Review Design", command=self.review_visual_design)
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        """Show enhanced context menu"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _create_enhanced_status_bar(self):
        """Create enhanced status bar"""
        status_frame = ttk.Frame(self)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_var = tk.StringVar(value="🚀 Enhanced Multi-Agent System Ready")
        status_bar = ttk.Label(
            status_frame, 
            textvariable=self.status_var,
            style="Status.TLabel", # Apply specific status bar label style
            anchor=tk.W
            # relief=tk.SUNKEN, # relief is handled by ttk style
            # padding=5 # padding is handled by ttk style
        )
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Agent status indicators (ttk.Label, will inherit general TLabel style)
        self.agent_status_frame = ttk.Frame(status_frame) # Will inherit TFrame style
        self.agent_status_frame.pack(side=tk.RIGHT, padx=5)

        # self.main_status_color_default and self.main_status_color_processing are now replaced by
        # self.agent_status_inactive_color and self.agent_status_active_color defined in __init__

        self.main_status = ttk.Label(self.agent_status_frame, text="🤖", foreground=self.agent_status_inactive_color)
        self.main_status.pack(side=tk.LEFT, padx=2)
        
        self.critic_status = ttk.Label(self.agent_status_frame, text="📊", foreground=self.agent_status_inactive_color)
        self.critic_status.pack(side=tk.LEFT, padx=2)
        
        self.art_status = ttk.Label(self.agent_status_frame, text="🎨", foreground=self.agent_status_inactive_color)
        self.art_status.pack(side=tk.LEFT, padx=2)

    def configure_enhanced_agents(self, api_key):
        """Configure enhanced multi-agent system"""
        try:
            self.agent_system = EnhancedMultiAgentSystem(api_key)
            self.status_var.set("✅ Enhanced Multi-Agent System configured")
            self.add_chat_message("System", "🚀 Enhanced Multi-Agent System ready!\n\n🤖 Main Coder Agent - Vision-enabled implementation\n📊 Code Critic Agent - Deep analysis & security\n🎨 Art Critic Agent - Visual analysis & design")
            self._draw_enhancer_toggle_switch() # Initial draw of the custom toggle switch
            self.update_agent_insights()
        except Exception as e:
            self.status_var.set(f"❌ Agent error: {str(e)}")
            self.add_chat_message("System", f"Agent configuration failed: {str(e)}", "#ff0000")

    def update_agent_insights(self):
        """Update project insights"""
        if not hasattr(self, 'agent_system'):
            return
            
        insights = []
        insights.append("📊 PROJECT ANALYSIS")
        insights.append("=" * 50)
        
        # File analysis
        file_count = len(self.agent_system._get_project_files())
        image_count = len(self.agent_system._get_project_images())
        insights.append(f"📁 Files: {file_count}")
        insights.append(f"🖼️ Images: {image_count}")
        
        # Recent changes
        recent_changes = len(self.agent_system._get_recent_changes())
        insights.append(f"🔄 Recent changes: {recent_changes}")
        
        # Agent capabilities
        insights.append("\n🤖 AGENT CAPABILITIES")
        insights.append("=" * 50)
        insights.append("🤖 Main Coder: Implementation + Vision")
        insights.append("📊 Code Critic: Quality + Security + Performance")
        insights.append("🎨 Art Critic: Visual Analysis + Design + UX")
        
        self.insights.config(state="normal")
        self.insights.delete("1.0", tk.END)
        self.insights.insert("1.0", "\n".join(insights))
        self.insights.config(state="disabled")

    def send_enhanced_prompt(self):
        """Send enhanced prompt to multi-agent system"""
        text = self.input_txt.get("1.0", tk.END).strip()
        if not text or text.startswith("💬 Ask the multi-agent"):
            return

        self.add_chat_message("👤 You", text, color=self.user_chat_color) # Use defined user color
        self.input_txt.delete("1.0", tk.END)

        self.input_txt.config(state="disabled")
        self.send_btn.config(state="disabled")
        self.screenshot_btn.config(state="disabled") # Disable screenshot button during processing
        self.status_var.set("🔄 Enhanced Multi-Agent System Processing...")

        # Update agent status to processing
                    # self.main_status.config(foreground=self.agent_status_active_color)
                    # self.critic_status.config(foreground=self.agent_status_active_color)
                    # self.art_status.config(foreground=self.agent_status_active_color)
                    # Initial status update will be handled by the agent_status_update message type

        threading.Thread(
            target=self._process_enhanced_prompt, 
            args=(text,),
            daemon=True
        ).start()

    def _process_enhanced_prompt(self, text):
        """Process enhanced prompt with multi-agent system"""
        if not hasattr(self, 'agent_system') or self.agent_system is None:
            self.msg_queue.put({"type": "error", "content": "Enhanced Multi-Agent System not configured. Set API key."})
            self.msg_queue.put({"type": "done"})
            return

        for response in self.agent_system.run_enhanced_interaction(text):
            self.msg_queue.put(response)
        self.msg_queue.put({"type": "done"})

    # This is the older _process_messages method that will be removed.
    # The newer one is further down, around line 2531.

    def display_enhanced_image(self, path):
        """Enhanced image display with metadata"""
        try:
            img = Image.open(path)
            original_size = img.size
            img.thumbnail((400, 300))

            self.canvas.delete("all")
            tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(200, 150, image=tk_img, anchor=tk.CENTER)
            self.canvas.image = tk_img

            # Add image metadata
            file_size = path.stat().st_size
            self.canvas.create_text(
                200, 280, 
                text=f"{path.name}\n{original_size[0]}x{original_size[1]}px\n{file_size:,} bytes", 
                fill="darkblue", 
                justify=tk.CENTER,
                font=("Arial", 9)
            )

            self.status_var.set(f"🖼️ Displaying: {path.name} ({original_size[0]}x{original_size[1]})")
        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(200, 150, text=f"❌ Error loading image:\n{str(e)}", 
                                   fill="red", justify=tk.CENTER)
            self.status_var.set(f"❌ Image error: {str(e)}")

    def refresh_files(self):
        """Enhanced file tree refresh with metadata"""
        self.tree.delete(*self.tree.get_children())
        self._populate_enhanced_tree(VM_DIR, "")

    def _populate_enhanced_tree(self, path, parent):
        """Enhanced tree population with file sizes"""
        for item in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if item.is_dir():
                node = self.tree.insert(
                    parent, 
                    'end', 
                    text=f"📁 {item.name}", 
                    values=(str(item.relative_to(VM_DIR)), ""), 
                    open=False
                )
                self._populate_enhanced_tree(item, node)
            else:
                try:
                    file_size = item.stat().st_size
                    size_str = self._format_file_size(file_size)
                    
                    if item.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        icon = "🖼️"
                    elif item.suffix.lower() in ['.py', '.js', '.html', '.css']:
                        icon = "📝"
                    else:
                        icon = "📄"
                        
                    node = self.tree.insert(
                        parent, 
                        'end', 
                        text=f"{icon} {item.name}", 
                        values=(str(item.relative_to(VM_DIR)), size_str)
                    )
                except OSError:
                    continue

    def _format_file_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def add_chat_message(self, sender, message, color="#000000"):
        """Enhanced chat message with better formatting"""
        self.chat.config(state="normal")
        
        # Create timestamp
        timestamp = time.strftime("[%H:%M:%S] ")
        
        # Configure tags
        # Use regex to create a safe tag name from the sender string
        safe_sender_name = re.sub(r'\W+', '', sender) # Remove non-alphanumeric
        sender_tag = f"sender_{safe_sender_name.strip()}"
        self.chat.tag_configure(sender_tag, foreground=color, font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("timestamp", foreground=self.timestamp_chat_color, font=("Segoe UI", 9)) # Use defined color
        self.chat.tag_configure("message", font=("Segoe UI", 11))
        
        # Insert message
        self.chat.insert(tk.END, timestamp, "timestamp")
        self.chat.insert(tk.END, f"{sender}:\n", sender_tag)
        self.chat.insert(tk.END, f"{message}\n\n", "message")
        
        self.chat.see(tk.END)
        self.chat.config(state="disabled")
        self.notebook.select(1)  # Switch to chat tab

    def _append_chat_chunk(self, sender, chunk_content, color="#000000"):
        """Appends a chunk of text to the chat, typically from a streaming response."""
        self.chat.config(state="normal")

        # Optimization: If the last message was from the same sender and also a chunk,
        # just append the text without new sender/timestamp.
        # This requires tracking the last message type/sender, or inspecting the Text widget.
        # For simplicity, this example will append each chunk as a new segment,
        # but prefix with a continuation character or similar if it's not the first chunk.

        # Check if this is the first chunk for this sender in this stream segment
        # A more robust way would be to manage state outside this function or pass a flag.
        # For now, we'll assume each call to this might be a new "start" of a chunk segment
        # or a continuation. A simple heuristic: if the last char is not a newline, it's a continuation.

        # A more complex check could involve tags:
        # last_char_index = self.chat.index(f"{tk.END}-2c") # -1c is newline, -2c is char before it
        # tags_on_last_char = self.chat.tag_names(last_char_index)
        # is_continuation = f"sender_chunk_{re.sub(r'\W+', '', sender)}" in tags_on_last_char

        # Simple approach: always append. The UI might look slightly disjointed for rapid chunks.
        # To make it smoother, one would manage a "current stream message" and append to its content.

        # For now, just append the content. Real-time display of agent name per chunk might be too noisy.
        # The `add_chat_message` handles sender name and timestamp.
        # This function is for the *content* of the stream.

        # We could consider a "start_stream" message type that prints "Agent X: "
        # and then agent_stream_chunk just appends content.

        # If the chat is empty or the last content was not from this agent streaming, print sender header.
        # This is a heuristic.
        current_chat_content = self.chat.get("1.0", tk.END).strip()
        if not current_chat_content.endswith(sender + ":\n"): # A bit simplistic
            # Check if the very last text inserted was for this agent's stream.
            # This is hard without more state.
            # Let's assume for now that the "agent_stream_chunk" is a signal to just append text.
            # The initial "Agent X:" would be printed by a regular "agent" message type if needed,
            # or we add a specific "agent_stream_start" message type.

            # If no prior message from this agent, or last message was different, print sender name.
            # This is a placeholder for better stream handling logic.
            # A better way: the first chunk could be a normal "agent" message, and subsequent ones "agent_stream_chunk"
            # which just appends. Or, _process_messages tracks current streaming agent.
            pass # For now, assume the calling logic handles the initial "Agent X:" part.

        self.chat.insert(tk.END, chunk_content, ("stream_chunk", color)) # Apply a generic stream_chunk tag + color
        self.chat.tag_configure("stream_chunk", foreground=color) # Ensure color is applied

        self.chat.see(tk.END)
        self.chat.config(state="disabled")
        if self.notebook.index(self.notebook.select()) != 1: # If chat tab is not selected
            self.notebook.select(1)


    # Additional enhanced methods
    def test_agent(self, agent_type):
        """Test individual agent functionality"""
        test_prompts = {
            "main": "Create a simple hello.py file with a greeting function",
            "critic": "Review the code quality of any Python files in the project",
            "art": "Analyze any images in the project and suggest visual improvements"
        }
        
        if agent_type in test_prompts:
            self.input_txt.delete("1.0", tk.END)
            self.input_txt.insert("1.0", test_prompts[agent_type])
            self.send_enhanced_prompt()

    def reset_agent_memory(self):
        """Reset agent conversation history"""
        if hasattr(self, 'agent_system'):
            self.agent_system.conversation_history = []
            self.agent_system.error_context = []
            self.add_chat_message("🔄 System", "Agent memory reset successfully")

    def show_project_stats(self):
        """Show detailed project statistics"""
        if not hasattr(self, 'agent_system'):
            return
            
        stats = []
        stats.append("📊 PROJECT STATISTICS")
        stats.append("=" * 40)
        
        files = self.agent_system._get_project_files()
        images = self.agent_system._get_project_images()
        
        stats.append(f"📁 Total Files: {len(files)}")
        stats.append(f"🖼️ Images: {len(images)}")
        
        if files:
            stats.append("\n📝 CODE FILES:")
            for f in files[:10]:  # Show first 10
                stats.append(f"  • {f}")
        
        if images:
            stats.append("\n🖼️ IMAGE FILES:")
            for img in images:
                stats.append(f"  • {img}")
        
        messagebox.showinfo("Project Statistics", "\n".join(stats))

    def show_agent_settings(self):
        """Show agent system settings with grading controls"""
        if not hasattr(self, 'agent_system'):
            messagebox.showwarning("⚠️ Warning", "Agent system not configured. Please set API key first.")
            return
            
        # Create settings dialog
        settings_window = tk.Toplevel(self)
        settings_window.title("🤖 Agent System Settings")
        settings_window.geometry("500x600")
        settings_window.transient(self)
        settings_window.grab_set()
        
        # Main content frame
        main_frame = ttk.Frame(settings_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🤖 ENHANCED MULTI-AGENT SYSTEM", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="📋 Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(config_frame, text=f"• Text Model: {TEXT_MODEL_NAME}").pack(anchor=tk.W)
        ttk.Label(config_frame, text=f"• Image Model: {IMAGE_MODEL_NAME}").pack(anchor=tk.W)
        ttk.Label(config_frame, text="• Vision Capabilities: ✅ Enabled").pack(anchor=tk.W)
        ttk.Label(config_frame, text="• Image Generation: ✅ Enabled").pack(anchor=tk.W)
        
        # Grading system section
        grading_frame = ttk.LabelFrame(main_frame, text="📊 Grading System", padding=10)
        grading_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.grading_var = tk.BooleanVar(value=getattr(self.agent_system, 'grading_enabled', True))
        grading_check = ttk.Checkbutton(
            grading_frame, 
            text="Enable Agent Grading & Retry System",
            variable=self.grading_var,
            command=self._toggle_grading
        )
        grading_check.pack(anchor=tk.W)
        
        # self.prompt_enhancer_var = tk.BooleanVar(value=getattr(self.agent_system, 'prompt_enhancer_enabled', True))
        # prompt_enhancer_check = ttk.Checkbutton(
        #     grading_frame,
        #     text="Enable Prompt Enhancer Agent ✨",
        #     variable=self.prompt_enhancer_var,
        #     command=self._toggle_prompt_enhancer
        # )
        # prompt_enhancer_check.pack(anchor=tk.W)

        ttk.Label(grading_frame, text=f"• Max Retry Attempts: {getattr(self.agent_system, 'max_retry_attempts', 3)}").pack(anchor=tk.W)
        ttk.Label(grading_frame, text="• Minimum Passing Grade: 70/100").pack(anchor=tk.W)
        
        # Agent capabilities section
        agents_frame = ttk.LabelFrame(main_frame, text="🎯 Agent Capabilities", padding=10)
        agents_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(agents_frame, text="• Main Coder: Implementation + Vision Analysis").pack(anchor=tk.W)
        ttk.Label(agents_frame, text="• Code Critic: Quality + Security + Performance + Grading").pack(anchor=tk.W)
        ttk.Label(agents_frame, text="• Art Critic: Visual Design + UX + Accessibility + Grading").pack(anchor=tk.W)
        
        # Memory section
        memory_frame = ttk.LabelFrame(main_frame, text="💾 Memory Status", padding=10)
        memory_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(memory_frame, text=f"• Conversation History: {len(getattr(self.agent_system, 'conversation_history', []))} entries").pack(anchor=tk.W)
        ttk.Label(memory_frame, text=f"• Error Context: {len(getattr(self.agent_system, 'error_context', []))} entries").pack(anchor=tk.W)
        
        # Features section
        features_frame = ttk.LabelFrame(main_frame, text="🔧 Features", padding=10)
        features_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(features_frame, text="• Enhanced syntax highlighting").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Auto-save functionality").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Visual file tree with metadata").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Real-time project insights").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Screenshot upload & analysis").pack(anchor=tk.W)
        
        # Close button
        close_btn = ttk.Button(main_frame, text="✅ Close", command=settings_window.destroy)
        close_btn.pack(pady=(20, 0))
        
    def _toggle_grading(self):
        """Toggle grading system on/off"""
        if hasattr(self, 'agent_system'):
            self.agent_system.grading_enabled = self.grading_var.get()
            status = "enabled" if self.grading_var.get() else "disabled"
            self.status_var.set(f"📊 Grading system {status}")
            self.add_chat_message("⚙️ Settings", f"Grading system {status}")

    def _toggle_prompt_enhancer(self, event=None):
        """Toggle prompt enhancer system on/off - called by the UI switch."""
        if hasattr(self, 'agent_system'):
            self.agent_system.prompt_enhancer_enabled = not self.agent_system.prompt_enhancer_enabled
            status = "enabled" if self.agent_system.prompt_enhancer_enabled else "disabled"
            self.status_var.set(f"✨ Prompt Enhancer {status}")
            self.add_chat_message("⚙️ Settings", f"Prompt Enhancer agent {status}")
            self._draw_enhancer_toggle_switch() # Update visual state of the switch

    # def _toggle_prompt_enhancer_menu(self): # Removed as toggle is no longer in menu
    #     """Toggle prompt enhancer system on/off - called by menu."""
    #     pass

    def _draw_enhancer_toggle_switch(self):
        """Draws the custom toggle switch based on the current state."""
        if not hasattr(self, 'enhancer_toggle_switch') or not hasattr(self, 'agent_system'):
            return # Not ready to draw

        self.enhancer_toggle_switch.delete("all") # Clear previous drawing

        # Get actual canvas dimensions as it's laid out
        self.enhancer_toggle_switch.update_idletasks() # Ensure dimensions are up-to-date
        width = self.enhancer_toggle_switch.winfo_width()
        height = self.enhancer_toggle_switch.winfo_height()

        if width <= 1 or height <= 1: # Canvas not yet sized by Tkinter
             # Fallback dimensions if still not available (should not happen often with update_idletasks)
            width = 50
            height = 22
            # self.enhancer_toggle_switch.after(50, self._draw_enhancer_toggle_switch)
            # return

        padding = 2
        oval_diameter = height - 2 * padding

        text_y_offset = height // 2

        if self.agent_system.prompt_enhancer_enabled:
            # Green background for "ON"
            self.enhancer_toggle_switch.create_rectangle(
                0, 0, width, height,
                fill="#4CAF50", outline="#388E3C", width=1 # Darker green for border
            )
            # White "ON" text
            self.enhancer_toggle_switch.create_text(
                (width - oval_diameter - padding) / 2, text_y_offset, text="ON", fill="white",
                font=("Segoe UI", 7, "bold"), anchor="center"
            )
            # Switch handle (oval) on the right
            self.enhancer_toggle_switch.create_oval(
                width - oval_diameter - padding, padding,
                width - padding, height - padding,
                fill="white", outline="#BDBDBD" # Light gray outline for handle
            )
        else:
            # Red background for "OFF"
            self.enhancer_toggle_switch.create_rectangle(
                0, 0, width, height,
                fill="#F44336", outline="#D32F2F", width=1 # Darker red for border
            )
            # White "OFF" text
            self.enhancer_toggle_switch.create_text(
                (width + oval_diameter + padding) / 2, text_y_offset, text="OFF", fill="white",
                font=("Segoe UI", 7, "bold"), anchor="center"
            )
            # Switch handle (oval) on the left
            self.enhancer_toggle_switch.create_oval(
                padding, padding,
                oval_diameter + padding, height - padding,
                fill="white", outline="#BDBDBD" # Light gray outline for handle
            )

    def analyze_selected_file(self):
        """Analyze selected file with agents"""
        selected = self.tree.selection()
        if not selected:
            return

        rel_path = Path(self.tree.item(selected[0], "values")[0])
        prompt = f"Please analyze the file '{rel_path}' and provide comprehensive feedback on code quality, design, and potential improvements."
        
        self.input_txt.delete("1.0", tk.END)
        self.input_txt.insert("1.0", prompt)
        self.send_enhanced_prompt()

    def review_visual_design(self):
        """Review visual design of selected file"""
        selected = self.tree.selection()
        if not selected:
            return

        rel_path = Path(self.tree.item(selected[0], "values")[0])
        if rel_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            prompt = f"Please analyze the visual design of '{rel_path}' image and provide detailed artistic feedback including composition, color theory, and suggestions for improvement."
        else:
            prompt = f"Please review '{rel_path}' for UI/UX design principles if it contains interface code, or suggest ways to make it more visually appealing."
        
        self.input_txt.delete("1.0", tk.END)
        self.input_txt.insert("1.0", prompt)
        self.send_enhanced_prompt()

    def prompt_api_key(self):
        """Enhanced API key prompt"""
        api_key = simpledialog.askstring(
            "🔑 API Key Configuration", 
            "Enter your Gemini API Key:\n(Required for multi-agent functionality)", 
            parent=self
        )
        if api_key:
            save_api_key(api_key)
            self.configure_enhanced_agents(api_key)
            messagebox.showinfo("✅ Success", "API Key saved and agents configured!")

    def on_tree_select(self, event):
        """Enhanced tree selection handler"""
        selected = self.tree.selection()
        if not selected:
            return

        rel_path = Path(self.tree.item(selected[0], "values")[0])
        file_path = VM_DIR / rel_path

        if file_path.is_file():
            if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                self.display_enhanced_image(file_path)
                self.current_open_file_path = None
                self.editor.delete("1.0", tk.END)
            else:
                self.display_file(file_path)

    def display_file(self, path):
        """Enhanced file display"""
        try:
            self.current_open_file_path = path
            content = path.read_text(encoding='utf-8')

            self.editor.config(state="normal")
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            self.editor.config(state="normal")

            self._apply_full_syntax_highlighting() # Changed here
            self.notebook.select(0)  # Switch to editor tab
            
            line_count = len(content.splitlines())
            char_count = len(content)
            self.status_var.set(f"📝 Loaded: {path.name} ({line_count} lines, {char_count} chars)")
        except UnicodeDecodeError:
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", "❌ Error reading file: File is not valid UTF-8 text.")
            self.status_var.set("❌ File error: Not a UTF-8 text file.")
            self.current_open_file_path = None
        except Exception as e:
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", f"❌ Error reading file: {str(e)}")
            self.status_var.set(f"❌ File error: {str(e)}")
            self.current_open_file_path = None

    def save_current_file(self):
        """Enhanced file saving"""
        if self.current_open_file_path and self.current_open_file_path.is_file():
            try:
                content = self.editor.get("1.0", tk.END)
                self.current_open_file_path.write_text(content, encoding='utf-8')
                
                line_count = len(content.splitlines())
                char_count = len(content)
                self.status_var.set(f"💾 Saved: {self.current_open_file_path.name} ({line_count} lines, {char_count} chars)")
                
                # Update insights
                self._schedule_update_insights()
            except Exception as e:
                self.status_var.set(f"❌ Save error: {str(e)}")
        else:
            self.status_var.set("❌ No file open to save")

    def new_file(self):
        """Enhanced new file creation"""
        file_name = simpledialog.askstring(
            "📄 New File", 
            "Enter file name (relative to project):\nTip: Include extension (.py, .js, .html, etc.)"
        )
        if file_name:
            if not hasattr(self, 'agent_system') or self.agent_system is None:
                messagebox.showerror("❌ Agent System Error", "Agent system not available. Cannot ensure safe path for new file.")
                return # Stop if agent system for _safe_path is not available

            file_path = self.agent_system._safe_path(file_name)
            if file_path:
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.touch()
                    self._schedule_refresh_files()
                    self.display_file(file_path)
                    self.status_var.set(f"✅ Created: {file_name}")
                    self._schedule_update_insights()
                except Exception as e:
                    self.status_var.set(f"❌ Error: {str(e)}")

    def rename_file(self):
        """Enhanced file renaming"""
        selected = self.tree.selection()
        if not selected:
            return

        old_rel_path = Path(self.tree.item(selected[0], "values")[0])
        old_full_path = VM_DIR / old_rel_path

        new_name = simpledialog.askstring(
            "📝 Rename File", 
            f"Renaming: {old_rel_path.name}\nEnter new name:", 
            initialvalue=old_rel_path.name
        )

        if new_name:
            new_full_path = old_full_path.parent / new_name
            try:
                old_full_path.rename(new_full_path)
                if self.current_open_file_path and self.current_open_file_path == old_full_path:
                    self.current_open_file_path = new_full_path
                self._schedule_refresh_files()
                self.status_var.set(f"✅ Renamed: {old_rel_path.name} → {new_name}")
                self._schedule_update_insights()
            except Exception as e:
                self.status_var.set(f"❌ Rename error: {str(e)}")

    def delete_file(self):
        """Enhanced file deletion"""
        selected = self.tree.selection()
        if not selected:
            return

        path_value = self.tree.item(selected[0], "values")[0]
        path_to_delete = Path(path_value)
        full_path_to_delete = VM_DIR / path_to_delete

        if messagebox.askyesno("🗑️ Confirm Deletion", f"Delete '{path_to_delete}'?\n\nThis action cannot be undone."):
            try:
                if full_path_to_delete.is_dir():
                    # shutil.rmtree is used for robust recursive directory deletion (already applied in a previous step)
                    # The file_count logic associated with the manual rmtree is no longer needed.
                    shutil.rmtree(full_path_to_delete) # Assuming this line was the intended state from previous step
                    self.status_var.set(f"✅ Deleted directory: {path_to_delete}")
                else:
                    file_size = full_path_to_delete.stat().st_size
                    full_path_to_delete.unlink()
                    self.status_var.set(f"✅ Deleted file: {path_to_delete} ({self._format_file_size(file_size)})")

                if self.current_open_file_path and self.current_open_file_path == full_path_to_delete:
                    self.editor.delete("1.0", tk.END)
                    self.current_open_file_path = None

                self._schedule_refresh_files()
                self._schedule_update_insights()
            except Exception as e:
                self.status_var.set(f"❌ Delete error: {str(e)}")

    def clear_chat(self):
        """Enhanced chat clearing"""
        if messagebox.askyesno("🧹 Clear Chat", "Clear all chat history?\n\nThis will also reset agent conversation memory."):
            self.chat.config(state="normal")
            self.chat.delete("1.0", tk.END)
            self.chat.config(state="disabled")
            
            if hasattr(self, 'agent_system'):
                self.agent_system.conversation_history = []
                self.agent_system.error_context = []
            
            self.add_chat_message("🔄 System", "Chat history and agent memory cleared")

    def upload_screenshot(self):
        """Automatic screenshot capture and insertion"""
        try:
            import subprocess
            import time
            import threading
            from tkinter import filedialog
            
            # Option 1: Auto-capture screenshot with Snipping Tool
            if messagebox.askyesno("📸 Screenshot Method", 
                                 "Choose screenshot method:\n\n" +
                                 "YES: Auto-capture with Snipping Tool\n" +
                                 "NO: Browse for existing image file"):
                
                self.status_var.set("📸 Starting screenshot capture...")
                self.screenshot_btn.config(state="disabled", text="📸 Capturing...")
                
                # Start screenshot capture in background thread
                threading.Thread(target=self._auto_capture_screenshot, daemon=True).start()
                
            else:
                # Option 2: Browse for existing file
                file_path = filedialog.askopenfilename(
                    title="Select Screenshot or Image",
                    filetypes=[
                        ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                        ("PNG files", "*.png"),
                        ("JPEG files", "*.jpg *.jpeg"),
                        ("All files", "*.*")
                    ]
                )
                
                if file_path:
                    self._process_uploaded_image(file_path)
                        
        except Exception as e:
            messagebox.showerror("❌ Screenshot Error", f"Screenshot functionality error: {str(e)}")
            self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")

    def _auto_capture_screenshot(self):
        """Automatically capture screenshot and save to project"""
        try:
            import subprocess
            import time
            from PIL import ImageGrab
            
            # Method 1: Try using PIL ImageGrab with clipboard after snipping tool
            try:
                # Launch Windows 10 Snipping Tool with clipboard copy
                subprocess.run(["snippingtool", "/clip"], shell=True, timeout=2)
                
                # Give user time to take screenshot
                time.sleep(0.5)
                
                # Monitor clipboard for screenshot
                self._monitor_clipboard_for_screenshot()
                
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                # Fallback: Try alternative snipping tool launch
                try:
                    subprocess.run(["snippingtool"], shell=True, timeout=2)
                    time.sleep(0.5)
                    self._monitor_clipboard_for_screenshot()
                    
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    # Final fallback: Manual file selection
                    self.msg_queue.put({
                        "type": "screenshot_error", 
                        "content": "Could not launch screenshot tool. Please use file browser option."
                    })
                    
        except Exception as e:
            self.msg_queue.put({
                "type": "screenshot_error", 
                "content": f"Screenshot capture error: {str(e)}"
            })

    def _monitor_clipboard_for_screenshot(self):
        """Monitor clipboard for screenshot and auto-save"""
        import time
        from PIL import ImageGrab
        
        max_wait_time = 30  # Wait up to 30 seconds for screenshot
        check_interval = 0.5  # Check every 0.5 seconds
        checks = 0
        max_checks = int(max_wait_time / check_interval)
        
        # Show user instruction
        self.msg_queue.put({
            "type": "screenshot_info", 
            "content": "Take your screenshot now - it will auto-save when ready..."
        })
        
        while checks < max_checks:
            try:
                # Try to get image from clipboard
                clipboard_image = ImageGrab.grabclipboard()
                
                if clipboard_image is not None:
                    # Successfully captured screenshot from clipboard
                    timestamp = int(time.time())
                    filename = f"screenshot_{timestamp}.png"
                    filepath = VM_DIR / filename
                    
                    # Save the image
                    clipboard_image.save(filepath, "PNG")
                    
                    # Queue success message and processing
                    self.msg_queue.put({
                        "type": "screenshot_success", 
                        "content": filename
                    })
                    return
                    
                time.sleep(check_interval)
                checks += 1
                
            except Exception as e:
                self.msg_queue.put({
                    "type": "screenshot_error", 
                    "content": f"Clipboard monitoring error: {str(e)}"
                })
                return
        
        # Timeout reached
        self.msg_queue.put({
            "type": "screenshot_timeout", 
            "content": "Screenshot capture timed out. Please try again or use file browser."
        })

    def _process_uploaded_image(self, file_path):
        """Process uploaded image file"""
        try:
            import shutil
            
            # Generate filename with timestamp
            timestamp = int(time.time())
            original_name = os.path.basename(file_path)
            name_parts = os.path.splitext(original_name)
            filename = f"screenshot_{timestamp}{name_parts[1]}"
            destination = VM_DIR / filename
            
            # Copy file to project directory
            shutil.copy2(file_path, destination)
            
            # Process the image
            self._finalize_screenshot_processing(filename)
            
        except Exception as e:
            messagebox.showerror("❌ Upload Error", f"Failed to process image: {str(e)}")

    def _finalize_screenshot_processing(self, filename):
        """Finalize screenshot processing and add to chat"""
        try:
            # Refresh files and display image
            self._schedule_refresh_files()
            filepath = VM_DIR / filename
            self.display_enhanced_image(filepath)
            
            # Auto-insert analysis prompt into text box
            analysis_prompt = f"Please analyze this screenshot '{filename}' and describe what you see, including any UI elements, code, text, or design patterns. Provide detailed feedback and suggestions for improvement."
            
            # Clear and set input text
            self._clear_placeholder(None)
            self.input_txt.delete("1.0", tk.END)
            self.input_txt.insert("1.0", analysis_prompt)
            
            # Add to chat history
            self.add_chat_message("📸 Auto-Screenshot", f"Screenshot captured and saved as '{filename}' - analysis prompt ready!")
            
            # Update status
            self.status_var.set(f"✅ Screenshot ready: {filename}")
            
            # Focus on input box for user to send
            self.input_txt.focus()
            
        except Exception as e:
            self.status_var.set(f"❌ Screenshot processing error: {str(e)}")

    def _process_messages(self):
        """Enhanced message processing with screenshot handling"""
        try:
            while not self.msg_queue.empty():
                msg = self.msg_queue.get_nowait()

                if msg["type"] == "agent":
                    agent_name = msg["agent"]
                    agent_colors = {
                        "🤖 Main Coder": "#2E8B57",
                        "📊 Code Critic": "#FF6347",
                        "🎭 Art Critic": "#9370DB",
                        "✨ Prompt Enhancer": "#FFD700", # Gold color for enhancer
                        "🤝 Collaborative": "#4169E1"
                    }
                    color = agent_colors.get(agent_name, self.fg_color_light) # Default to fg_color_light
                    self.add_chat_message(agent_name, msg["content"], color)
                elif msg["type"] == "agent_stream_chunk":
                    agent_name = msg["agent"]
                    # Determine color based on agent, similar to "agent" type
                    agent_colors = {
                        "🤖 Main Coder": "#2E8B57", # Example color
                        # Add other agents if they also stream
                    }
                    color = agent_colors.get(agent_name, self.fg_color_light)
                    self._append_chat_chunk(agent_name, msg["content"], color)
                elif msg["type"] == "system":
                    self.add_chat_message("🔧 System", msg["content"], color=self.system_chat_color) # Use defined system color
                elif msg["type"] == "error":
                    error_content = msg.get("content", "An unspecified error occurred.")
                    self.add_chat_message("❌ Error", error_content, color=self.error_chat_color)
                    # Set agent icons to error color
                    self.main_status.config(foreground=self.agent_status_error_color)
                    self.critic_status.config(foreground=self.agent_status_error_color)
                    self.art_status.config(foreground=self.agent_status_error_color)
                    error_summary = str(error_content).split('\n')[0]
                    self.status_var.set(f"❌ Error: {error_summary[:100]}") # Update status bar text
                elif msg["type"] == "agent_status_update":
                    agent_name = msg["agent"]
                    status = msg["status"]

                    agent_display_names = {
                        "main_coder": "🤖 Main Coder",
                        "code_critic": "📊 Code Critic",
                        "art_critic": "🎨 Art Critic",
                        "art_critic_proactive": "🎨 Art Critic (Proactive)",
                        "prompt_enhancer": "✨ Prompt Enhancer"
                    }
                    display_name = agent_display_names.get(agent_name, agent_name)

                    target_widget = None
                    if agent_name == "main_coder":
                        target_widget = self.main_status
                    elif agent_name == "code_critic":
                        target_widget = self.critic_status
                    elif agent_name == "art_critic" or agent_name == "art_critic_proactive":
                        target_widget = self.art_status
                    elif agent_name == "prompt_enhancer":
                        target_widget = self.main_status

                    if target_widget:
                        if status == "active":
                            target_widget.config(foreground=self.agent_status_active_color)
                            self.status_var.set(f"{display_name} processing...")
                        elif status == "inactive":
                            target_widget.config(foreground=self.agent_status_inactive_color)
                            # Set a generic processing message if the system isn't fully done or in an error state.
                            # This helps bridge the gap between one agent finishing and another starting, or before the final "done" message.
                            # Only update to generic "processing..." if a specific agent is not currently active.
                            # This check is imperfect as it doesn't know the state of *other* agents,
                            # but it's better than always overwriting an active agent's status.
                            if f"{display_name} processing..." == self.status_var.get():
                                 self.status_var.set("🔄 Enhanced Multi-Agent System processing...")
                elif msg["type"] == "screenshot_success":
                    filename = msg["content"]
                    self._finalize_screenshot_processing(filename)
                    self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")
                elif msg["type"] == "screenshot_error":
                    self.add_chat_message("❌ Screenshot Error", msg["content"], "#ff0000")
                    self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")
                elif msg["type"] == "screenshot_timeout":
                    self.add_chat_message("⏰ Screenshot Timeout", msg["content"], "#ff6600")
                    self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")
                elif msg["type"] == "screenshot_info":
                    self.status_var.set(msg["content"])
                elif msg["type"] == "file_changed":
                    self._schedule_refresh_files()
                    self._schedule_update_insights()
                    changed_file_path = Path(msg["content"])
                    if changed_file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        self.display_enhanced_image(changed_file_path)
                    elif self.current_open_file_path and self.current_open_file_path.samefile(changed_file_path):
                        self.display_file(self.current_open_file_path)
                elif msg["type"] == "done":
                    self.input_txt.config(state="normal")
                    self.send_btn.config(state="normal")
                    self.status_var.set("✅ Enhanced Multi-Agent System Ready")
                    # Reset agent status icons (already handled by individual 'inactive' messages from run_enhanced_interaction)
                    self.main_status.config(foreground=self.agent_status_inactive_color)
                    self.critic_status.config(foreground=self.agent_status_inactive_color)
                    self.art_status.config(foreground=self.agent_status_inactive_color)

        except queue.Empty:
            pass

        self.after(100, self._process_messages)

    def on_close(self):
        """Enhanced close handler, ensures pending 'after' calls are cancelled."""
        if messagebox.askokcancel("🚪 Exit", "Exit Enhanced Multi-Agent IDE?\n\nUnsaved changes will be lost."):
            # Cancel any pending debounced calls
            if self._debounce_refresh_id:
                self.after_cancel(self._debounce_refresh_id)
                self._debounce_refresh_id = None
            if self._debounce_insights_id:
                self.after_cancel(self._debounce_insights_id)
                self._debounce_insights_id = None

            # Cancel auto-save timer
            if hasattr(self, '_save_timer') and self._save_timer: # Check if _save_timer exists and is not None
                self.after_cancel(self._save_timer)
                self._save_timer = None

            self.destroy()

# -----------------------------------------------------------------------------
# Application Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    VM_DIR.mkdir(exist_ok=True)
    app = EnhancedGeminiIDE()
    app.mainloop()
