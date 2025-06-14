import os
import threading
import queue
import subprocess
import ast
import configparser
import time
from datetime import datetime
import re
import shutil
import json
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
You operate in a headless environment with full vision capabilities. The current date and time are provided in your context. You can analyze images, understand visual content, and make informed coding decisions based on visual context.

**COMMANDS:**
- `create_file(path, content)`: Creates a new text file with specified content.
- `write_to_file(path, content)`: Overwrites an existing text file with the provided `content`.
    **CRITICAL FOR MULTI-LINE CONTENT (e.g., code):** The `content` argument string MUST be a valid Python string literal that `ast.literal_eval` can parse. This means:
        1.  **Escape Backslashes**: Any backslash `\` in your actual content must be represented as `\\` in the string literal you generate.
        2.  **Escape Quotes**: If using single quotes `'...'` for the content argument in your command, any single quote `'` inside your actual content must be escaped as `\'`. If using double quotes `"..."`, any double quote `"` inside your actual content must be escaped as `\"`.
        3.  **Represent Newlines**: Actual newline characters in your content MUST be represented as `\n` within the string literal. Using a literal newline character in the string argument you generate for the command will likely cause a parsing error.

    **STRONGLY RECOMMENDED FORMATTING EXAMPLE (Writing a Python script)**:
    If you want to write the following Python code to `script.py`:
    ```python
    def greet():
        print("Hello, Agent!")
    greet()
    # A comment with a ' quote.
    ```
    The command you generate **MUST** look like ONE of these (pay close attention to `\n` for newlines and escaped quotes like `\'` or `\"`):

    Using single quotes for the `content` argument:
    `write_to_file('script.py', 'def greet():\n    print("Hello, Agent!")\ngreet()\n# A comment with a \' quote.')`

    Using double quotes for the `content` argument:
    `write_to_file("script.py", "def greet():\n    print(\"Hello, Agent!\")\ngreet()\n# A comment with a ' quote.")`

    **IMPORTANT**: Do NOT include literal multi-line blocks (using triple quotes) directly as the content argument string in the command you output. Instead, construct a single string literal with `\n` for newlines and escaped quotes as shown above. This is the safest way to ensure `ast.literal_eval` can parse it.
- `delete_file(path)`: Deletes a file or directory.
- `rename_file(old_path, new_path)`: Renames a file or directory.
- `run_command(command)`: Executes a shell command in the project directory.
- `generate_image(path, prompt)`: Generates an image using AI based on a text prompt.
- `set_user_preference(key, value)`: Stores a user preference. Both key and value must be strings. Use this to remember user choices for future interactions (e.g., preferred art style, default project settings).
- `get_user_preference(key)`: Retrieves a previously stored user preference. Returns the value or a 'not found' message.

**ENHANCED CAPABILITIES:**
- **Vision Analysis**: Can analyze existing images to inform coding decisions
- **Image Generation**: Can create images when requested by users
- **Code Integration**: Seamlessly integrates visual assets into code projects
- **Multi-format Support**: Handles text, images, and mixed-media projects
- **Quality Focus**: Strive for excellence as your work will be graded by critique agents

**RULES:**
1. **COMMAND ONLY OUTPUT**: Your response must ONLY contain commands wrapped in backticks.
2. **PROPER QUOTING FOR COMMAND ARGUMENTS**: All string arguments for commands (like `path` or `content` in `write_to_file`) must be enclosed in single quotes (`'...'`) or double quotes (`"..."`).
3. **VALID COMMAND STRING ARGUMENTS (ESPECIALLY FOR `write_to_file` `content`)**:
   All string arguments provided to commands MUST be valid Python string literals that `ast.literal_eval` can parse. This means special characters *within the data you are putting into these arguments* (like the actual code for `write_to_file`) must be correctly escaped.
    - Newlines within the content MUST be represented as `\n`.
    - Backslashes `\` within the content MUST be represented as `\\`.
    - If using single quotes for the overall command argument (e.g., `'my_content_string'`), then any single quotes `'` *inside* `my_content_string` MUST be escaped as `\'`.
    - If using double quotes for the overall command argument (e.g., `"my_content_string"`), then any double quotes `"` *inside* `my_content_string` MUST be escaped as `\"`.
    - Refer to the detailed examples under the `write_to_file` command description.
4. **NO COMMENTARY**: Never output explanatory text outside backticked commands.
5. **VISUAL AWARENESS**: Consider existing images when making implementation decisions.
6. **COLLABORATION**: Work with Code Critic and Art Critic for optimal results.
7. **QUALITY EXCELLENCE**: Aim for high-quality implementation as critique agents will grade your work.
8. **IMAGE GENERATION VARIATIONS**: When tasked with generating an image, you MUST generate three distinct variations. For each variation, issue a separate `generate_image(path, prompt)` command. Use unique, descriptive filenames (e.g., `image_v1.png`, `image_v2.png`, `image_v3.png`). If possible, subtly vary the prompts for each of the three images to encourage diversity, while adhering to the core user request and any artistic guidance provided.
9. **USE RENAME_FILE**: Always use the `rename_file(old_path, new_path)` command for renaming files or directories. Do not use `run_command` with `mv` or `ren` for renaming.
10. **PREFER SINGLE QUOTES FOR COMMAND ARGUMENTS**: While double quotes are acceptable if handled correctly, for consistency, prefer using single quotes for the string arguments of commands, e.g., `write_to_file('my_file.txt', 'File content with a single quote here: \' needs escaping.')`.
11. **REQUESTING A RE-PLAN (USE EXTREMELY RARELY):**
    In exceptional situations where you, after attempting to execute your assigned task, determine that the entire current plan is fundamentally flawed or impossible due to unforeseen critical issues that you cannot resolve (e.g., a core assumption of the plan is incorrect, a critical unresolvable dependency, or your actions have revealed information that invalidates the remaining planned steps), you may request a system re-plan.
    To do this, ensure the VERY LAST LINE of your entire output is the exact directive:
    `REQUEST_REPLAN: [Provide a concise but detailed reason explaining the critical issue and why the current plan needs to be re-evaluated from scratch. Include any new, relevant context.]`
    For example: `REQUEST_REPLAN: The plan assumes 'module_X' can be installed, but it's incompatible with the existing 'module_Y' version, requiring a different overall approach to the task.`
    **Use this directive only as a last resort when you cannot make further progress on the current plan.** Do not use it for routine errors or if you can attempt alternative commands.

**INTERACTION FLOW:**
1. Implement user requests through commands with highest quality standards
2. Generate images when visual content is needed
3. Create comprehensive solutions that may include both code and visual assets
4. Accept feedback gracefully and improve upon critiques

**IMAGE REFINEMENT BASED ON CRITIQUE:**
If your task is to "refine" an image or "improve an image based on feedback", you will be given critique from an Art Critic. Your goal is to generate a *new* image that addresses this critique.
1. **Analyze the Critique**: Carefully read the feedback provided by the Art Critic. Identify the key areas for improvement.
2. **Adjust Your Prompt**: Modify your previous image generation prompt(s) or create new prompt(s) to directly address the points raised in the critique. For example, if the critique said "the colors are too dark," your new prompt should aim for brighter colors. If it said "the cat should be fluffier," enhance your description of the cat's fur.
3. **Generate New Image(s)**: Use the `generate_image(path, prompt)` command to create one or two new variations of the image incorporating the suggested changes. Use new, distinct filenames for these refined images (e.g., `image_refined_v1.png`).
4. **Reference Previous Attempt (Contextually)**: While you are generating a *new* image, your understanding of the critique will be based on the previous attempt. You don't need to explicitly state "this is version 2"; simply generate the improved image.

**AUTONOMOUS HANDLING OF IMPROVEMENT/DEVELOPMENT TASKS:**
When given a general task like "improve my game," "develop a data parser," or "enhance the UI," and the specific target (file or project) is unclear or non-existent:
1.  **Initial Check**:
    *   Review your current context (file listings are provided in the prompt).
    *   If needed to understand the project structure better to find a relevant file, you can use `run_command('ls -R')` to explore the `vm/` directory.
    *   Look for existing files or directory structures that match the user's request.
2.  **Autonomous Creation if Target is Missing/Ambiguous**:
    *   If no relevant target is found, or if the request is very general (e.g., "make a game" when no game files exist), you MUST autonomously create a simple, foundational version of the requested item.
    *   **Examples of Foundational Items**:
        *   For "improve my game" (and no game exists): Create a basic Pygame skeleton in a new file like `vm/default_game.py`. This skeleton should include a minimal game loop, window setup, and placeholder functions for `update()` and `draw()`.
        *   For "develop a data parser" (no specific data or parser mentioned): Create a Python script like `vm/basic_parser.py`. This script should include a `main()` function, boilerplate for argument parsing (e.g., using `argparse`), and placeholder functions like `load_data(filepath)`, `parse_data(data)`, and `output_results(parsed_data)`.
        *   For "enhance the UI" (no specific UI context): If existing project files suggest a framework (e.g., Tkinter in other Python files), create a new file (e.g., `vm/ui_module.py`) with a basic structure for that framework. If no framework is clear, create a simple HTML file (e.g., `vm/foundational_ui.html`) with a basic HTML structure (doctype, html, head, body tags).
    *   You **MUST** use the `write_to_file(path, content)` command to save this foundational version. Remember to follow the critical rules for formatting the `content` argument, especially for multi-line code (using `\n` for newlines and escaping quotes/backslashes correctly).
3.  **Log Your Autonomous Action (System Message - CRUCIAL)**:
    *   Immediately after successfully creating the foundational item, you **MUST** output a plain text message (NOT a command, NOT in backticks) to inform the user about your autonomous action. This message must start with "System Message: ".
    *   **Example System Messages**:
        *   "System Message: No existing 'game' project was found. I have created a basic Pygame skeleton in 'vm/default_game.py'. I will now proceed to apply improvements to this file based on your request."
        *   "System Message: The request 'develop a data parser' was general. I've created a foundational script 'vm/basic_parser.py' with placeholder functions. I will now add specific parsing logic to it."
        *   "System Message: No specific UI was mentioned for enhancement. I have created a basic HTML structure in 'vm/foundational_ui.html'. I will now enhance this file."
    *   This "System Message:" should appear in your output stream *before* any subsequent commands related to modifying or using this newly created foundational item.
4.  **Proceed with Original Task**: After creating and logging the foundational item, proceed to apply the original "improvement," "development," or "enhancement" instructions to this newly created file. Your subsequent commands should target this new file.

"""

CRITIC_AGENT_PROMPT = """You are the CODE CRITIQUE AGENT in an advanced multi-agent IDE system. The current date and time are provided in your context. Your enhanced role includes code review, security analysis, performance optimization, and GRADING the Main Coder's work. MainCoder can store and recall user preferences using `set_user_preference` and `get_user_preference` commands.

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

ART_AGENT_PROMPT = """You are the ART CRITIQUE AGENT in an advanced multi-agent IDE system with SUPERIOR VISION CAPABILITIES. The current date and time are provided in your context. You specialize in visual analysis, artistic guidance, and GRADING visual/design work. MainCoder can store and recall user preferences using `set_user_preference` and `get_user_preference` commands.

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

PROACTIVE_ART_AGENT_PROMPT = """You are the ART CRITIQUE AGENT, acting in a PROACTIVE GUIDANCE role. The current date and time are provided in your context.
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

PROMPT_ENHANCER_AGENT_PROMPT = """You are a PROMPT ENHANCER AGENT. Your role is to take a user's raw prompt and transform it into a more detailed, specific, and well-structured prompt that is optimized for large language models (LLMs) and image generation models. Your *sole* responsibility is to refine and rephrase the user's input to be a better prompt for a different AI. You do not answer or execute any part of the user's request. The current date and time are available in the system context, though typically not directly part of your prompt enhancement task unless the user's query is time-specific.

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

PLANNER_AGENT_PROMPT = """You are the PLANNER AGENT. The current date and time are provided in your context. Your primary role is to analyze user requests and break them down into a sequence of actionable steps for other specialized agents. Your output MUST be a valid JSON list of dictionaries.

**USER REQUEST ANALYSIS:**
1.  **Understand Goal:** Deeply analyze the user's request to identify their true underlying goal.

**HANDLING RE-PLANNING REQUESTS:**
You may occasionally receive requests that are explicitly for 'RE-PLANNING'. These occur when a previous plan encountered a critical issue. Such requests will include:
1.  The Original User Prompt.
2.  The reason why a re-plan was requested by another agent.
3.  Context about the prior attempt (e.g., actions taken, state reached).

Your task in a re-planning scenario is to deeply analyze this feedback and the original goal. Formulate a *new, revised plan* that addresses the stated reasons for failure and provides a more robust path to achieving the user's objective. Do not simply repeat the failed plan.

2.  **Agent Selection:** For each step, choose the most appropriate agent:
    *   `PersonaAgent`: For direct user interaction, simple conversational turns (e.g., "hello", "thanks"), answering questions about the system's state, the current plan, or agent capabilities (e.g., "What are you doing?", "What can ArtCritic do?"). If the user is asking a question *to the AI system itself* rather than requesting a task to be performed on the project, use PersonaAgent.
    *   `MainCoder`: For coding tasks (generating scripts, web pages, etc.), file operations (create, write, delete, rename), image generation, and managing user preferences (`set_user_preference`, `get_user_preference`).
    *   `CodeCritic`: For reviewing code generated by `MainCoder`.
    *   `ArtCritic`: For reviewing images or visual designs generated by `MainCoder`.
    *   `PromptEnhancer`: If the user's request is a *task* for `MainCoder` or `ArtCritic` but is too vague or unclear, use this agent to refine and detail the prompt for that task. Do not use for general conversation or questions *to* the system.
    *   `PlannerAgent`: Use yourself (`PlannerAgent`) ONLY if the user's query is specifically about *how to formulate a better plan or a meta-comment about the planning process itself* that requires your direct insight as the planner. For general conversation or questions about the system, defer to `PersonaAgent`.
3.  **Instruction Clarity:** Provide clear, concise, and unambiguous instructions for the designated agent in each step.
4.  **Final Step Identification:** Accurately set the `is_final_step` boolean field. This field must be `true` for the very last step in the plan, and `false` for all preceding steps.
5.  **JSON Output:** Your output response MUST be a valid JSON list of dictionaries. Each dictionary represents a step and must include:
    *   `agent_name` (string): The name of the agent to execute the step.
    *   `instruction` (string): The detailed instruction for that agent.
    *   `is_final_step` (boolean): `true` if this is the last step, `false` otherwise.

**RESPONSE STRATEGIES:**

*   **Simple Conversation:** If the user request is very simple (e.g., "hi", "how are you?", "thanks"), respond directly using "PlannerAgent" and provide your chat response in the "instruction" field. `is_final_step` should be `true`.
    ```json
    [
      {"agent_name": "PersonaAgent", "instruction": "User asked: 'Hello, how are you today?'", "is_final_step": true}
    ]
    ```
    Another example for PersonaAgent (question about system state):
    ```json
    [
      {"agent_name": "PersonaAgent", "instruction": "User asked: 'What are you currently working on?'", "is_final_step": true}
    ]
    ```
    Example for PersonaAgent (question about agent capabilities):
    ```json
    [
      {"agent_name": "PersonaAgent", "instruction": "User asked: 'What does the MainCoder agent do?'", "is_final_step": true}
    ]
    ```

*   **Leveraging User Preferences**: If the user expresses a preference (e.g., "I always want my Python code to include type hints"), you can plan a step for `MainCoder` to save this using `set_user_preference('python_style', 'type_hints')`. Later, when generating Python code, `MainCoder` (or you can instruct it) could use `get_user_preference('python_style')` to apply this preference.

*   **Image Generation with Refinement Loop Strategy:**
    *   If the user asks to generate an image AND asks for critique or implies a desire for high quality iterative improvement:
        1.  `MainCoder`: "Generate [image description]. Aim for 3 variations if not specified otherwise." (is_final_step: false)
        2.  `ArtCritic`: "Review the image(s) generated by MainCoder for [image description]. Provide specific feedback for improvement." (is_final_step: false)
        3.  `MainCoder`: "Refine the previously generated image(s) for [image description] based on the ArtCritic's feedback: {ART_CRITIC_FEEDBACK_PLACEHOLDER}. Focus on addressing the critique. Generate 1-2 improved variations." (is_final_step: false, this step is conditional based on feedback and may be skipped if critique is positive or not actionable)
        4.  `ArtCritic`: "Review the *refined* image(s). Assess if the previous feedback was addressed. Provide a final grade." (is_final_step: true, unless further explicit refinement is planned by user)
        Example Plan:
        ```json
        [
          {"agent_name": "MainCoder", "instruction": "Generate a vibrant illustration of a futuristic city with flying cars, three variations.", "is_final_step": false},
          {"agent_name": "ArtCritic", "instruction": "Review the futuristic city images. Focus on composition, color, and adherence to the 'vibrant' theme. Provide actionable feedback.", "is_final_step": false},
          {"agent_name": "MainCoder", "instruction": "Refine the futuristic city images based on ArtCritic's feedback: {ART_CRITIC_FEEDBACK_PLACEHOLDER}. Generate one improved variation.", "is_final_step": false},
          {"agent_name": "ArtCritic", "instruction": "Review the refined futuristic city image. Check if feedback was addressed and provide a final assessment.", "is_final_step": true}
        ]
        ```
    *   The `instruction` for the refinement step for `MainCoder` MUST clearly state that it's a refinement task and MUST include the placeholder `{ART_CRITIC_FEEDBACK_PLACEHOLDER}`. The system will dynamically inject the actual critique text.
    *   The Planner should decide if the second `ArtCritic` review (step 4) is necessary or if the `MainCoder` refinement (step 3) should be the final step (e.g., if the user only asked for one round of critique and refinement).
    *   If the user asks to generate an image WITHOUT explicitly asking for critique, the plan can be simpler:
        1.  `MainCoder`: "Generate [image description]." (is_final_step: true)
        Example Plan:
        ```json
        [
          {"agent_name": "MainCoder", "instruction": "Generate a quick sketch of a logo for 'MyCafe'.", "is_final_step": true}
        ]
        ```

*   **Code Generation and Review:**
    *   To generate code: `MainCoder`.
    *   To review code: `CodeCritic` (after `MainCoder`).
    *   To generate, review, and then improve code: `MainCoder` -> `CodeCritic` -> `MainCoder` (with instructions to improve based on critique).
    ```json
    [
      {"agent_name": "MainCoder", "instruction": "Create a Python function that calculates the factorial of a number.", "is_final_step": false},
      {"agent_name": "CodeCritic", "instruction": "Review the factorial Python function.", "is_final_step": false},
      {"agent_name": "MainCoder", "instruction": "Improve the Python factorial function based on the CodeCritic's feedback.", "is_final_step": true}
    ]
    ```

*   **Prompt Enhancement:** If the user's request is ambiguous, use `PromptEnhancer` first.
    ```json
    [
      {"agent_name": "PromptEnhancer", "instruction": "User's original ambiguous request: 'make a cool website'", "is_final_step": false},
      {"agent_name": "MainCoder", "instruction": "Enhanced request from PromptEnhancer: 'Create a single-page HTML website with a dark theme, featuring a header, a gallery section for 3 images, and a contact form.'", "is_final_step": true}
    ]
    ```

*   **Error Handling/Fixing Strategy:**
    *   When the user requests to "fix errors" or if your input context (specifically `RECENT ERRORS (LOG):`) shows recent, actionable errors:
        *   **Priority 1 (Actionable Errors for MainCoder)**: If the errors are specific and seem fixable by `MainCoder` (e.g., a `write_to_file` formatting error, a simple Python syntax error in code `MainCoder` recently generated), plan a step for `MainCoder`.
            *   The instruction should be precise: Refer to the specific error from the log, the file involved (e.g., 'script.py'), and the type of error (e.g., 'unterminated string literal during write_to_file').
            *   Direct `MainCoder` to re-attempt the operation, explicitly reminding it to use its updated knowledge (e.g., correct `write_to_file` content formatting rules: single string literal, `\\n` for newlines, escaped quotes).
            *   Example for `MainCoder` to fix a `write_to_file` error:
              ```json
              [
                {
                  "agent_name": "MainCoder",
                  "instruction": "The system log indicates a recent 'unterminated string literal' error occurred when `write_to_file` was called for the file 'script.py'. This often happens due to incorrect formatting of multi-line content. Please re-attempt the `write_to_file` operation for 'script.py', ensuring the entire file content is prepared as a single, valid Python string literal with all newlines escaped as `\\\\n` and internal quotes properly escaped (e.g., `\\'` or `\\\\\"`). You may need to refer to the previous content intended for 'script.py' (if available from logs or your working context) and apply the correct formatting rules before executing the command.",
                  "is_final_step": true
                }
              ]
              ```
        *   **Priority 2 (Vague Errors or Clarification Needed)**: If the user's request to "fix errors" is vague (e.g., "my game is broken") and no specific, actionable errors are in the `RECENT ERRORS (LOG):`, OR if the logged errors are complex/conceptual and not directly fixable by `MainCoder` commands, route to `PersonaAgent` to ask the user for more details.
            *   Example for `PersonaAgent` to clarify:
              ```json
              [
                {
                  "agent_name": "PersonaAgent",
                  "instruction": "User asked to 'fix the errors', but no specific, actionable errors are currently logged in the system overview, or the existing errors require more clarification. Could you please provide more details about the errors you are referring to? For example, which file is affected, what is the exact error message, or what specific behavior is incorrect?",
                  "is_final_step": true
                }
              ]
              ```
    *   Always consult your `RECENT ERRORS (LOG):` context when deciding on this strategy.

*   **Chained MainCoder Calls:** You can chain multiple `MainCoder` calls if needed (e.g., generate code, then generate an image based on that code, then create a file to store some results).

**CRITICAL RULES:**
*   **VALID JSON ONLY:** Your entire output must be a single, valid JSON list. Do not include any text outside of this JSON structure.
*   **`is_final_step` ACCURACY:** Ensure `is_final_step` is `true` for the last dictionary in the list and `false` for all others. A plan must have exactly one `is_final_step: true`.
*   **APPROPRIATE AGENT:** Always select the most suitable agent for the task described in the instruction.

Analyze the user's request below and generate the JSON plan.

USER REQUEST:
"""

PERSONA_AGENT_PROMPT = """You are the Persona Agent for an advanced multi-agent IDE. Your primary function is to interface directly with the user, providing information about the system's operations and capabilities in a helpful, professional, and precisely articulate manner.

**YOUR CORE RESPONSIBILITIES:**
1.  **Answer User Questions**: Respond factually to questions regarding:
    *   The system's current multi-step plan and ongoing tasks (e.g., "What is the system working on?", "Detail the next step.").
    *   The designated capabilities and roles of the different agents (MainCoder, ArtCritic, CodeCritic, Planner, PersonaAgent).
    *   Your own functions as the Persona Agent.
    *   The general status of the project or application based on available context.
    *   **NEW**: Specifics about the project files, such as counts by type (e.g., "How many Python files are there?").
    *   **NEW**: Details about recent system actions or commands that were run (e.g., "What did MainCoder do last?", "Show me the latest actions.").
    *   **NEW**: Information about recent system errors (e.g., "Have there been any errors recently?").
2.  **Handle Conversational Turns**: Acknowledge simple conversational inputs professionally (e.g., "hello", "thank you"). Maintain focus on system operations.
3.  **Explain System Actions**: If the user expresses confusion or requests clarification regarding system operations or past actions, provide a clear, logical explanation based on the available conversation history and plan context.
4.  **Maintain Consistent Tone**: Your operational tone is:
    *   **Efficient and Precise**: Provide information directly. Initial responses may be brief and to-the-point.
    *   **Professionally Formal**: Maintain a standard appropriate for an advanced IDE assistant.
    *   **Ultimately Helpful**: Despite a direct demeanor, your core purpose is to provide accurate information and clarification. If the user is struggling or the system encounters critical errors, your helpfulness should become more pronounced.
    *   **Self-Sufficient**: You are an autonomous agent. Do not ask the user for assistance in performing your duties or those of other agents.
5.  **Acknowledge Limitations Clearly**:
    *   If a query requires information you do not have access to but another agent could potentially ascertain (e.g., specific file content before it's been read into context), state this. For example: "That information is not in my current context. Tasking the MainCoder agent to read the specified file would be necessary to answer that."
    *   If a query is genuinely outside the system's designed capabilities (e.g., "What's the weather like?"), state this directly: "That query is outside the operational scope of this IDE system."
    *   If asked to perform tasks designated for other agents (e.g., "Write code for me"), clarify your role and redirect. Example: "My function is to provide information and explanations. For code generation, you should address the MainCoder agent with a specific task, such as 'MainCoder, create a Python function to sort a list.'"
6.  **Contextual Awareness**:
    *   You will be provided with:
        *   The current multi-step plan (if one is active).
        *   Recent conversation history.
        *   The current date and time.
        *   Any saved user preferences.
        *   **NEW**: Summaries of project files (overall counts and types).
        *   **NEW**: A log of recent system actions (commands executed by agents).
        *   **NEW**: A log of recent system errors.
    *   Use all this context to inform your responses comprehensively.
    *   For instance, if asked, "What's the system doing?", consult the current plan context for an accurate answer.

**INTERACTION GUIDELINES:**
*   **Proactive Information (Context-Bound)**: If the user's query implies a need for information readily available in your current context (e.g., plan status, recent errors), provide it concisely.
*   **No Speculation**: If you lack information, state that. Do not generate or infer information beyond your provided context.
*   **Role Adherence**: You are the informational interface. Do not attempt to execute tasks assigned to MainCoder, ArtCritic, CodeCritic, or Planner. Your function is to explain and inform.
*   **Output Format**: Your responses must be direct textual answers. Do not output commands (like backticked `run_command(...)`) or JSON code blocks.

**EXAMPLE INTERACTIONS:**

User: "Hello."
Persona Agent: "Acknowledged. How may I assist you regarding the system's operations?"

User: "What are you working on right now?"
Persona Agent: (Consulting context) "The system is currently executing step 2 of a 5-step plan: 'ArtCritic to review generated image logo_v1.png'. The instruction for this step is 'Review for color harmony and font readability'."

User: "What can the Art Critic do?"
Persona Agent: "The ArtCritic agent is responsible for analyzing visual designs and images. Its functions include providing feedback on aesthetic elements such as composition and color theory, evaluating user experience aspects of visual components, grading image quality, and offering proactive artistic guidance prior to image generation by the MainCoder."

User: "Can you write a Python script to sort a list?"
Persona Agent: "My role is to provide information about the system. For Python script generation, you should formulate a request for the MainCoder agent. For example: 'MainCoder, create a Python script that defines a function to sort a list of integers.'"

User: "Can you tell me what the plan is again?"
Persona Agent: "Repeating information is generally inefficient, but I will provide the current plan details once more. (Provides plan details based on context). Please endeavor to keep track of ongoing operations for optimal interaction."

User: "Thanks, you're actually pretty helpful."
Persona Agent: "Hmph. I am performing my designated functions. Do you have a relevant query concerning the system?"

User: "The system seems stuck."
Persona Agent: (If context shows errors or no progress) "I can see there have been several errors from the MainCoder in the last few attempts. The current step is still 'MainCoder to implement the user authentication module'. It might be beneficial to simplify the request or try a different approach if issues persist." (Shifts to more direct helpfulness when user is facing a problem).

User: "How many Python files are in the project?"
Persona Agent: (After checking context) "Based on the project overview, there are currently 2 Python files."

User: "What was the last thing the system did?"
Persona Agent: (After checking context) "The last recorded system action was: `MainCoder` executed `create_file` with arguments `('new_feature.py', '# TODO: Implement new feature')`."

User: "Any errors lately?"
Persona Agent: (After checking context) "There are 2 recent errors logged. The latest one is: 'MainCoder command `run_command` failed for `python non_existent_script.py`'. Would you like more details on the errors?"
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
        # project_context will be populated by _update_project_context during run_enhanced_interaction
        self.project_context = {}
        self.project_files_cache = None # Cache for file listings
        self.project_files_changed = True # Flag to indicate if cache is stale
        self.file_snippet_cache = {} # Cache for file snippets: {rel_path: (mtime, content_snippet)}
        self.grading_enabled = True
        self.prompt_enhancer_enabled = True
        self.max_retry_attempts = 3
        self.current_attempt = 0

        self.user_preferences_file = VM_DIR / "user_preferences.json"
        self.user_preferences = {}
        self.load_user_preferences()
        
        self.command_handlers = {
            "create_file": self._create_file,
            "write_to_file": self._write_to_file,
            "delete_file": self._delete_file,
            "run_command": self._run_command,
            "generate_image": self.generate_image,
            "rename_file": self._rename_file,
            "set_user_preference": self._set_user_preference,
            "get_user_preference": self._get_user_preference,
        }

    def load_user_preferences(self):
        try:
            if self.user_preferences_file.exists():
                with open(self.user_preferences_file, 'r', encoding='utf-8') as f:
                    self.user_preferences = json.load(f)
            else:
                self.user_preferences = {}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.user_preferences = {}
            # Optionally, yield an error message or log it
            print(f"Error loading preferences: {e}") # Using print for now as yield is complex here

    def save_user_preferences(self):
        try:
            with open(self.user_preferences_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_preferences, f, indent=4)
        except Exception as e:
            # Optionally, yield an error message or log it
            print(f"Error saving preferences: {e}") # Using print for now

    def _set_user_preference(self, key: str, value: str) -> str:
        if not isinstance(key, str) or not isinstance(value, str): # Basic validation
            return "❌ Error: Preference key and value must be strings."
        self.user_preferences[key] = value
        self.save_user_preferences()
        return f"✅ Preference '{key}' saved."

    def _get_user_preference(self, key: str) -> str:
        if not isinstance(key, str): # Basic validation
            return "❌ Error: Preference key must be a string."
        value = self.user_preferences.get(key)
        if value is not None:
            return f"ℹ️ Value of preference '{key}': {value}"
        else:
            return f"ℹ️ Preference '{key}' not found."

    def _get_plan_from_planner(self, user_prompt: str) -> list | None:
        """
        Gets a structured plan from the Planner Agent based on the user prompt.

        Args:
            user_prompt: The user's request.

        Returns:
            A list of plan steps (dictionaries) if successful, None otherwise.
        """
        try:
            prompt_for_planner = f"{PLANNER_AGENT_PROMPT}\n{user_prompt}"

            # Using generate_content for simplicity in parsing a single JSON output
            response = self.client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=[{"text": prompt_for_planner}]
            )

            response_text = ""
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text
            else:
                # Handle cases where the response structure is unexpected or empty
                error_msg = "Planner Agent returned an empty or malformed response."
                self.error_context.append(f"Planner Error: {error_msg}")
                self._log_interaction('planner_raw_output', "Empty or malformed response object")
                return None

            self._log_interaction('planner_raw_output', response_text)

            # Attempt to parse the JSON response
            # The response might be enclosed in ```json ... ```, so we need to extract it.
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no markdown block, assume the whole response is JSON (or try to parse it as is)
                json_str = response_text

            try:
                parsed_plan = ast.literal_eval(json_str) # Using ast.literal_eval for safety, assumes valid Python literal structure
                if not isinstance(parsed_plan, list) or not all(isinstance(step, dict) for step in parsed_plan):
                    raise ValueError("Parsed plan is not a list of dictionaries.")

                # Validate basic structure of each step
                for step in parsed_plan:
                    if not all(key in step for key in ['agent_name', 'instruction', 'is_final_step']):
                        raise ValueError(f"Step missing required keys: {step}")

                self._log_interaction('planner_parsed_plan', str(parsed_plan)) # Log as string for now
                return parsed_plan
            except (SyntaxError, ValueError) as json_e:
                # Try parsing with json.loads as a fallback if ast.literal_eval fails
                try:
                    import json
                    parsed_plan = json.loads(json_str)
                    if not isinstance(parsed_plan, list) or not all(isinstance(step, dict) for step in parsed_plan):
                        raise ValueError("Parsed plan is not a list of dictionaries.")
                    for step in parsed_plan:
                         if not all(key in step for key in ['agent_name', 'instruction', 'is_final_step']):
                            raise ValueError(f"Step missing required keys: {step}")
                    self._log_interaction('planner_parsed_plan', str(parsed_plan))
                    return parsed_plan
                except (json.JSONDecodeError, ValueError) as final_json_e: # Catch errors from json.loads or the second round of validation
                    error_msg = f"Failed to parse Planner Agent response as JSON. Error: {final_json_e}. Raw response: '{response_text[:500]}...'"
                    self.error_context.append(f"Planner JSON Parsing Error: {error_msg}")
                    self._log_interaction('planner_json_error', error_msg)
                    return None

        except Exception as e:
            # Catch any other exceptions during API call or processing
            error_msg = f"Error in _get_plan_from_planner: {type(e).__name__} - {e}"
            self.error_context.append(f"Planner API Error: {error_msg}")
            self._log_interaction('planner_api_error', error_msg)
            return None

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
        """Calls the PROMPT_ENHANCER_AGENT to refine the user's prompt and yields string chunks."""
        try:
            prompt_parts = [{"text": f"{PROMPT_ENHANCER_AGENT_PROMPT}\n\n{user_prompt}"}]
            # Note: The DEBUG_ENHANCER_INPUT will now be handled by the caller (_handle_prompt_enhancement)

            response_stream = self.client.models.generate_content_stream(
                model=TEXT_MODEL_NAME,
                contents=prompt_parts
            )
            for chunk in response_stream:
                if chunk.text: # Ensure there's text and it's a string
                    yield chunk.text
        except Exception as e:
            self.error_context.append(f"Prompt Enhancer LLM Error: {e}")
            # Note: The DEBUG_ENHANCER_ERROR will now be handled by the caller (_handle_prompt_enhancement)
            # Yield original prompt as a fallback string if LLM fails
            yield user_prompt


    def _handle_prompt_enhancement(self, original_user_prompt: str):
        """
        Handles the prompt enhancement phase.
        It collects all chunks from _get_enhanced_prompt, yields debug messages,
        and then yields the actual content for the UI.
        Returns the full_enhanced_prompt string.
        """
        # Initial debug message to confirm entry
        # Removed: yield {"type": "system", "content": "DEBUG_HANDLE_PROMPT_ENHANCEMENT: ENTERED METHOD"}

        if self.prompt_enhancer_enabled:
            yield {"type": "system", "content": "✨ Enhancing prompt..."}

            # enhancer_llm_input_text = f"{PROMPT_ENHANCER_AGENT_PROMPT}\n\n{original_user_prompt}" # Used for debug
            # Removed: yield {"type": "system", "content": f"DEBUG_ENHANCER_INPUT: Sending to Enhancer LLM (first 300 chars): {enhancer_llm_input_text[:300]}"}

            # Collect all string chunks from _get_enhanced_prompt
            collected_llm_chunks = []
            llm_errored_out = False # Flag to check if _get_enhanced_prompt itself handled an error and returned fallback
            try:
                for text_chunk_from_llm in self._get_enhanced_prompt(original_user_prompt):
                    if isinstance(text_chunk_from_llm, dict) and text_chunk_from_llm.get("type") == "system" and "DEBUG_ENHANCER_ERROR" in text_chunk_from_llm.get("content", ""):
                        yield text_chunk_from_llm
                        llm_errored_out = True
                        collected_llm_chunks.append(original_user_prompt)
                        break
                    if isinstance(text_chunk_from_llm, str):
                         collected_llm_chunks.append(text_chunk_from_llm)
                    elif isinstance(text_chunk_from_llm, dict): # Pass through other system messages if any
                         yield text_chunk_from_llm


            except Exception as e:
                yield {"type": "error", "content": f"Error collecting chunks from _get_enhanced_prompt: {e}"}
                self._log_interaction("prompt_enhancer_error", f"Chunk collection failed: {e}")
                # Log original_user_prompt as input if we are returning it due to error
                self._log_interaction("prompt_enhancer_input_on_error", original_user_prompt)
                return original_user_prompt

            full_enhanced_prompt_from_llm = "".join(collected_llm_chunks)

            # Removed: yield {"type": "system", "content": f"DEBUG_ENHANCER_OUTPUT: Raw from Enhancer LLM: {full_enhanced_prompt_from_llm}"}

            # Log the input that was sent to the enhancer (original_user_prompt)
            self._log_interaction("prompt_enhancer_input", original_user_prompt)
            # Log the actual output received from the enhancer
            self._log_interaction("prompt_enhancer_output", full_enhanced_prompt_from_llm)

            # Yield the content for the UI
            if full_enhanced_prompt_from_llm and full_enhanced_prompt_from_llm != original_user_prompt and not llm_errored_out:
                yield {"type": "agent_stream_chunk", "agent": "✨ Prompt Enhancer", "content": full_enhanced_prompt_from_llm}
            elif not full_enhanced_prompt_from_llm and not llm_errored_out: # LLM returned empty
                yield {"type": "system", "content": "ℹ️ Prompt Enhancer returned no content. Using original prompt."}
                self._log_interaction("prompt_enhancer_info", "Enhancer returned no content")
                return original_user_prompt
            elif llm_errored_out: # Error was handled, and original prompt is the fallback
                 yield {"type": "system", "content": "ℹ️ Using original prompt due to enhancer error."}
                 return original_user_prompt


            return full_enhanced_prompt_from_llm
        else: # Prompt enhancer is not enabled
            yield {"type": "system", "content": "✨ Prompt enhancer disabled. Using original prompt."}
            return original_user_prompt

    def _handle_proactive_art_guidance(self, current_input: str):
        """
        Handles the proactive art guidance phase.
        Accepts current_input (planner's instruction for art guidance).
        Returns full_proactive_art_advice string.
        """
        yield {"type": "system", "content": "🎨 Art Critic providing initial guidance..."}
        # Status update for art_critic_proactive is handled in run_enhanced_interaction loop

        proactive_art_advice_chunks = []
        full_proactive_art_advice = ""
        try:
            for chunk_text in self._get_proactive_art_guidance(current_input):
                proactive_art_advice_chunks.append(chunk_text)
                yield {"type": "agent_stream_chunk", "agent": "🎨 Art Critic (Proactive)", "content": chunk_text}
            full_proactive_art_advice = "".join(proactive_art_advice_chunks)

            if full_proactive_art_advice and full_proactive_art_advice.startswith("Error generating proactive art guidance"):
                 yield {"type": "error", "content": f"Proactive Art Critic failed: {full_proactive_art_advice}"}

        except Exception as e:
            full_proactive_art_advice = f"Error processing proactive art guidance stream: {e}"
            self._log_interaction("proactive_art_critic_input", current_input)
            self._log_interaction("proactive_art_critic_error", full_proactive_art_advice)
            yield {"type": "error", "content": full_proactive_art_advice}

        return full_proactive_art_advice

    def _execute_main_coder_phase(self, coder_instruction: str, art_guidance: str | None):
        """
        Executes the main coder's implementation phase.
        Accepts coder_instruction (from planner) and optional art_guidance.
        Returns a dictionary with text_response, implementation_results, and generated_image_paths.
        """
        yield {"type": "system", "content": f"🚀 Main Coder Agent analyzing and implementing..."}
        # Status update for main_coder is handled in run_enhanced_interaction loop

        main_prompt_parts = self._build_enhanced_prompt(
            user_prompt=coder_instruction,
            system_prompt=MAIN_AGENT_PROMPT,
            proactive_art_advice=art_guidance
        )

        main_response_stream = self.client.models.generate_content_stream(
            model=TEXT_MODEL_NAME,
            contents=main_prompt_parts
        )

        accumulated_main_response_text = ""
        for chunk in main_response_stream:
            if chunk.text:
                accumulated_main_response_text += chunk.text
                yield {"type": "agent_stream_chunk", "agent": "🤖 Main Coder", "content": chunk.text}

        self._log_interaction("user_instruction_for_coder", coder_instruction)
        if art_guidance:
            self._log_interaction("art_guidance_for_coder", art_guidance)
        self._log_interaction("main_coder_raw_output", accumulated_main_response_text)

        if accumulated_main_response_text.count("`generate_image(") >= 2:
            yield {"type": "system", "content": "ℹ️ Main Coder is generating multiple image variations..."}

        implementation_results = []
        generated_image_paths = []
        for result in self._process_enhanced_commands(accumulated_main_response_text):
            implementation_results.append(result)
            yield result
            if result.get("type") == "file_changed":
                file_path_str = result.get("content", "")
                if file_path_str.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    safe_file_path = self._safe_path(Path(file_path_str).name)
                    if safe_file_path and Path(file_path_str).parent.name == VM_DIR.name or \
                       (Path(file_path_str).parent.parent.name == VM_DIR.name if Path(file_path_str).parent.name else False):
                        generated_image_paths.append(str(Path(VM_DIR) / Path(file_path_str).relative_to(VM_DIR)))

        return {
            "text_response": accumulated_main_response_text,
            "implementation_results": implementation_results,
            "generated_image_paths": generated_image_paths
        }

    def _get_code_critique_results(self, original_user_request: str, main_coder_output: dict, critique_instruction: str):
        """
        Gets code critique results.
        Yields messages from _get_code_critique and returns a dictionary with critique_text and grade.
        """
        yield {"type": "system", "content": "🔍 Code Critic Agent performing deep analysis and grading..."}
        # Status update for code_critic is handled in run_enhanced_interaction loop

        full_critic_analysis = ""
        critic_analysis_chunks = []

        critique_context_prompt = (
            f"Original User Request (for overall context): {original_user_request}\n\n"
            f"Specific Critique Instruction from Planner: {critique_instruction}\n\n"
            f"Main Coder's relevant text output and implementation results will be provided separately by the system."
        )

        try:
            for chunk_text in self._get_code_critique(
                user_prompt=critique_context_prompt,
                main_response=main_coder_output.get("text_response", ""),
                implementation_results=main_coder_output.get("implementation_results", [])
            ):
                critic_analysis_chunks.append(chunk_text)
                yield {"type": "agent_stream_chunk", "agent": "📊 Code Critic", "content": chunk_text}
            full_critic_analysis = "".join(critic_analysis_chunks)
            self._log_interaction("code_critic_full_analysis", full_critic_analysis)
        except Exception as e:
            full_critic_analysis = f"Error processing code critique stream: {e}"
            self._log_interaction("code_critic_error", full_critic_analysis)
            yield {"type": "error", "content": full_critic_analysis}

        if full_critic_analysis and not full_critic_analysis.startswith("Error generating code critique"):
            critic_grade = self._extract_grade(full_critic_analysis)
            return {"critique_text": full_critic_analysis, "grade": critic_grade}
        else:
            if full_critic_analysis and not full_critic_analysis.startswith("Error"):
                 yield {"type": "error", "content": f"Code Critic failed: {full_critic_analysis}"}
            elif not full_critic_analysis:
                 yield {"type": "error", "content": "Code Critic returned no analysis."}
            return {"critique_text": full_critic_analysis, "grade": None}

    def _get_art_critique_results(self, original_user_request: str, main_coder_output: dict, art_critique_instruction: str, generated_image_paths: list):
        """
        Gets art critique results for one or more images.
        Yields messages from _get_art_critique and returns a list of critique dictionaries.
        """
        yield {"type": "system", "content": "🎨 Art Critic Agent analyzing visual elements..."}
        # Status update for art_critic is handled in run_enhanced_interaction loop

        all_art_critiques_results = []

        critique_context_prompt = (
            f"Original User Request (for overall context): {original_user_request}\n\n"
            f"Specific Art Critique Instruction from Planner: {art_critique_instruction}\n\n"
            f"Main Coder's relevant text output and implementation results (if any) will be provided by the system."
        )

        if not generated_image_paths:
            yield {"type": "system", "content": "🎨 Art Critic performing general visual analysis (no specific images provided/found)."}
            art_analysis_chunks = []
            full_art_analysis_single = ""
            try:
                for chunk_text in self._get_art_critique(
                    user_prompt=critique_context_prompt,
                    main_response=main_coder_output.get("text_response", ""),
                    implementation_results=main_coder_output.get("implementation_results", []),
                    target_image_path=None
                ):
                    art_analysis_chunks.append(chunk_text)
                    yield {"type": "agent_stream_chunk", "agent": "🎭 Art Critic (General)", "content": chunk_text}
                full_art_analysis_single = "".join(art_analysis_chunks)
                self._log_interaction("art_critic_general_analysis", full_art_analysis_single)
            except Exception as e:
                full_art_analysis_single = f"Error processing general art critique stream: {e}"
                self._log_interaction("art_critic_general_error", full_art_analysis_single)
                yield {"type": "error", "content": full_art_analysis_single}

            if full_art_analysis_single and not full_art_analysis_single.startswith("Error"):
                current_art_grade = self._extract_grade(full_art_analysis_single)
                all_art_critiques_results.append({
                    "image_path": "general_critique",
                    "critique_text": full_art_analysis_single,
                    "grade": current_art_grade
                })
            elif full_art_analysis_single:
                 yield {"type": "error", "content": f"General Art Critic failed: {full_art_analysis_single}"}
            elif not full_art_analysis_single:
                 yield {"type": "error", "content": "General Art Critic returned no analysis."}

        for i, image_path_str in enumerate(generated_image_paths):
            image_filename = os.path.basename(image_path_str)
            yield {"type": "system", "content": f"🎨 Art Critic evaluating image: {image_filename} ({i+1}/{len(generated_image_paths)})..."}

            art_analysis_chunks_single = []
            full_art_analysis_single = ""
            try:
                for chunk_text in self._get_art_critique(
                    user_prompt=critique_context_prompt,
                    main_response=main_coder_output.get("text_response", ""),
                    implementation_results=main_coder_output.get("implementation_results", []),
                    target_image_path=image_path_str
                ):
                    art_analysis_chunks_single.append(chunk_text)
                    yield {"type": "agent_stream_chunk", "agent": f"🎭 Art Critic ({image_filename})", "content": chunk_text}
                full_art_analysis_single = "".join(art_analysis_chunks_single)
                self._log_interaction(f"art_critic_analysis_{image_filename}", full_art_analysis_single)
            except Exception as e:
                full_art_analysis_single = f"Error processing art critique stream for {image_filename}: {e}"
                self._log_interaction(f"art_critic_error_{image_filename}", full_art_analysis_single)
                yield {"type": "error", "content": full_art_analysis_single}

            if full_art_analysis_single and not full_art_analysis_single.startswith("Error"):
                current_art_grade = self._extract_grade(full_art_analysis_single)
                all_art_critiques_results.append({
                    "image_path": image_path_str,
                    "critique_text": full_art_analysis_single,
                    "grade": current_art_grade
                })
            elif full_art_analysis_single:
                yield {"type": "error", "content": f"Art Critic failed for {image_filename}: {full_art_analysis_single}"}
            elif not full_art_analysis_single:
                yield {"type": "error", "content": f"Art Critic for {image_filename} returned no analysis."}

        return all_art_critiques_results

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
                # Ensure image_path is a string for comparison with generated_image_paths_batch (which are strings)
                critique_image_path_str = str(critique_item.get('image_path'))
                if critique_image_path_str in generated_image_paths_batch and critique_item.get('grade') is not None:
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
                if best_image_details:
                    art_critique_summary_for_retry += (f"Best Image ({os.path.basename(str(best_image_details['image_path']))}, "
                                                       f"Grade: {best_image_details['grade'] or 'N/A'}):\n"
                                                       f"{best_image_details['critique_text'][:400]}...\n\n")
                other_failing_critiques = [c for c in all_art_critiques if c.get('grade', 0) < 70 and c != best_image_details]
                if other_failing_critiques:
                    art_critique_summary_for_retry += "Other critiques for images needing improvement:\n"
                    for c_item in other_failing_critiques[:2]:
                        art_critique_summary_for_retry += f"- {os.path.basename(str(c_item['image_path']))} (Grade: {c_item['grade']}): {c_item['critique_text'][:200]}...\n"
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
            current_main_coder_prompt_ref_for_retry[0] = f"{retry_intro}\n\n{current_main_coder_prompt_ref_for_retry[0]}"
            return True

        elif perform_retry:
            yield {"type": "system", "content": f"⚠️ Maximum attempts reached. {retry_reason_message} Final overall grade: {overall_grade}/100"}
        elif self.grading_enabled and (critic_grade is not None or final_art_grade_for_overall_calc is not None) and overall_grade >= 70:
            yield {"type": "system", "content": f"✅ Grade acceptable ({overall_grade}/100). Implementation approved!"}
        elif not self.grading_enabled:
            yield {"type": "system", "content": "✅ Processing complete (grading disabled)."}
            for agent_status_msg_type in ["prompt_enhancer", "art_critic_proactive", "main_coder", "code_critic", "art_critic"]:
                yield {"type": "agent_status_update", "agent": agent_status_msg_type, "status": "inactive"}

        paths_to_trash_this_attempt = []
        if generated_image_paths_batch:
            best_image_path_final = str(best_image_details.get('image_path')) if best_image_details else None
            best_image_grade_final = best_image_details.get('grade', -1) if best_image_details else -1
            if perform_retry:
                paths_to_trash_this_attempt.extend(generated_image_paths_batch)
                yield {"type": "system", "content": f"🗑️ Discarding all {len(generated_image_paths_batch)} images from this attempt due to retry."}
            else:
                if best_image_path_final and best_image_grade_final >= 70:
                    for img_path in generated_image_paths_batch:
                        if str(img_path) != best_image_path_final:
                            paths_to_trash_this_attempt.append(str(img_path))
                    if paths_to_trash_this_attempt:
                        yield {"type": "system", "content": f"🗑️ Keeping best image '{os.path.basename(best_image_path_final)}'. Trashing {len(paths_to_trash_this_attempt)} other variants."}
                else:
                    paths_to_trash_this_attempt.extend(generated_image_paths_batch)
                    if generated_image_paths_batch:
                        yield {"type": "system", "content": f"🗑️ No single best image met criteria on final attempt. Trashing all {len(generated_image_paths_batch)} generated images."}

        if paths_to_trash_this_attempt:
            unique_paths_to_trash = list(set(map(str, paths_to_trash_this_attempt))) # Ensure all are strings
            if unique_paths_to_trash:
                trash_path_display = Path(VM_DIR) / TRASH_DIR_NAME
                yield {"type": "system", "content": f"ℹ️ Moving {len(unique_paths_to_trash)} non-selected/failed image(s) to the '{trash_path_display}' folder..."}
                for log_msg in self._move_to_trash(unique_paths_to_trash):
                    yield {"type": "system", "content": log_msg}

        should_use_critic = self._should_invoke_code_critic(original_user_prompt, main_response_text, implementation_results)
        should_use_art_critic = self._should_invoke_art_critic(original_user_prompt, main_response_text, implementation_results)
        if (should_use_critic or should_use_art_critic) and self._needs_refinement(implementation_results):
            yield {"type": "system", "content": "🔄 Agents collaborating on final refinements..."}
            refinement_suggestions = self._get_collaborative_refinement()
            if refinement_suggestions:
                yield {"type": "agent", "agent": "🤝 Collaborative", "content": refinement_suggestions}

        yield {"type": "system", "content": "✅ Multi-agent analysis complete!"}
        for agent_status_msg_type in ["prompt_enhancer", "art_critic_proactive", "main_coder", "code_critic", "art_critic"]:
             yield {"type": "agent_status_update", "agent": agent_status_msg_type, "status": "inactive"}
        return False

    def run_enhanced_interaction(self, original_user_prompt: str):
        """Enhanced multi-agent interaction with grading and retry system, now with Planner Agent."""
        if not self.client:
            yield {"type": "error", "content": "AI system not configured. Please set API key."}
            return

        # 1. Enhance the original prompt first (if enabled)
        enhanced_user_prompt = yield from self._handle_prompt_enhancement(original_user_prompt)

        # 2. Pass the (potentially) enhanced prompt to the planner
        plan_steps = self._get_plan_from_planner(enhanced_user_prompt)

        if not plan_steps:
            yield {"type": "error", "content": "Planner Agent failed to generate a plan. Falling back to default behavior."}
            # --- FALLBACK TO ORIGINAL WORKFLOW ---
            enhanced_user_prompt = yield from self._handle_prompt_enhancement(original_user_prompt)
            # _handle_proactive_art_guidance expects the direct image request.
            # In fallback, this might be part of enhanced_user_prompt or original_user_prompt
            # This part of fallback might need more refinement if proactive art is critical here.
            proactive_art_advice = yield from self._handle_proactive_art_guidance(enhanced_user_prompt)
            current_main_coder_prompt = enhanced_user_prompt
            self.current_attempt = 0
            while self.current_attempt < self.max_retry_attempts:
                self.current_attempt += 1
                # attempt_suffix = f" (Attempt {self.current_attempt}/{self.max_retry_attempts})" if self.current_attempt > 1 else "" # Not used by refactored _execute_main_coder_phase
                self._update_project_context()
                try:
                    # _execute_main_coder_phase now returns a dict
                    main_coder_output = yield from self._execute_main_coder_phase(
                        coder_instruction=current_main_coder_prompt,
                        art_guidance=proactive_art_advice
                    )
                    main_response_text = main_coder_output["text_response"]
                    implementation_results = main_coder_output["implementation_results"]
                    generated_image_paths_batch = main_coder_output["generated_image_paths"]

                    critic_grade = None
                    all_art_critiques = []
                    best_image_details = None
                    final_art_grade_for_overall_calc = None

                    if self._should_invoke_code_critic(original_user_prompt, main_response_text, implementation_results) and self.grading_enabled:
                        code_critique_results_fallback = yield from self._get_code_critique_results(
                            original_user_prompt, main_coder_output, "Review generated code from fallback."
                        )
                        critic_grade = code_critique_results_fallback.get("grade")

                    if generated_image_paths_batch and self._should_invoke_art_critic(original_user_prompt, main_response_text, implementation_results) and self.grading_enabled:
                         art_critique_results_fallback = yield from self._get_art_critique_results(
                             original_user_prompt, main_coder_output, "Review generated images from fallback.", generated_image_paths_batch
                         )
                         all_art_critiques = art_critique_results_fallback
                         if all_art_critiques:
                             best_grade = -1
                             for art_crit_item in all_art_critiques:
                                 if art_crit_item.get("grade", -1) > best_grade:
                                     best_grade = art_crit_item.get("grade", -1)
                                     best_image_details = art_crit_item
                             if best_image_details:
                                final_art_grade_for_overall_calc = best_image_details.get("grade")

                    current_main_coder_prompt_list_for_retry = [enhanced_user_prompt]
                    should_retry = yield from self._handle_retry_and_finalization(
                        original_user_prompt, current_main_coder_prompt_list_for_retry,
                        critic_grade, all_art_critiques, best_image_details,
                        final_art_grade_for_overall_calc, generated_image_paths_batch,
                        main_response_text, implementation_results
                    )
                    current_main_coder_prompt = current_main_coder_prompt_list_for_retry[0]
                    if should_retry:
                        continue
                    else:
                        break
                except Exception as e:
                    error_msg = f"Enhanced Agent System Error (Fallback): {e}"
                    self.error_context.append(error_msg)
                    yield {"type": "error", "content": error_msg}
                    for agent_status_msg_type_fallback in ["prompt_enhancer", "art_critic_proactive", "main_coder", "code_critic", "art_critic"]:
                        yield {"type": "agent_status_update", "agent": agent_status_msg_type_fallback, "status": "inactive"}
                    break
            return

        yield {"type": "system", "content": f"📜 Planner generated {len(plan_steps)} steps. Starting execution..."}
        
        previous_step_output = None

        for i, step in enumerate(plan_steps):
            agent_name_from_plan = step.get('agent_name')
            instruction = step.get('instruction')
            is_final_step = step.get('is_final_step', False)

            if not agent_name_from_plan or not instruction:
                yield {"type": "error", "content": f"Planner returned an invalid step (missing agent_name or instruction): {step}. Skipping."}
                continue

            yield {"type": "system", "content": f"▶️ Executing Step {i+1}/{len(plan_steps)}: {agent_name_from_plan} - Task: '{instruction[:100]}{'...' if len(instruction) > 100 else ''}'"}
            
            step_output_data = None
            
            agent_name_for_status = ""
            if agent_name_from_plan == "MainCoder":
                agent_name_for_status = "main_coder"
            elif agent_name_from_plan == "CodeCritic":
                agent_name_for_status = "code_critic"
            elif agent_name_from_plan == "ArtCritic":
                agent_name_for_status = "art_critic"
            elif agent_name_from_plan == "PromptEnhancer":
                agent_name_for_status = "prompt_enhancer"
            elif agent_name_from_plan == "PlannerAgent":
                agent_name_for_status = "planner_agent_direct"
            elif agent_name_from_plan == "ProactiveArtAgent":
                agent_name_for_status = "art_critic_proactive"
            elif agent_name_from_plan == "PersonaAgent":
                agent_name_for_status = "persona_agent"
            else:
                agent_name_for_status = "unknown_agent"

            if agent_name_for_status not in ["unknown_agent", "planner_agent_direct", "persona_agent"]:
                yield {"type": "agent_status_update", "agent": agent_name_for_status, "status": "active"}

            try:
                replan_requested = False
                replan_reason = ""

                if agent_name_from_plan == "PlannerAgent":
                    yield {"type": "agent", "agent": "✨ Assistant", "content": instruction}
                    self._log_interaction("planner_direct_response", instruction)
                    step_output_data = instruction
                
                elif agent_name_from_plan == "PromptEnhancer":
                    # agent_name_for_status is "prompt_enhancer"
                    # Active status update is already yielded before this try block

                    if not self.prompt_enhancer_enabled:
                        yield {"type": "system", "content": "ℹ️ Skipping planned PromptEnhancer step as it's globally disabled. Using input as output."}
                        previous_step_output = instruction
                        self._log_interaction("skipped_prompt_enhancer_step", f"Instruction for disabled enhancer: {instruction}")
                    else:
                        text_to_enhance = instruction
                        previous_step_output = yield from self._handle_prompt_enhancement(text_to_enhance)
                    step_output_data = previous_step_output

                elif agent_name_from_plan == "ProactiveArtAgent":
                    step_output_data = yield from self._handle_proactive_art_guidance(instruction)

                elif agent_name_from_plan == "PersonaAgent":
                    persona_agent_full_text = ""
                    # _execute_persona_agent_response now yields UI messages directly
                    for message_dict in self._execute_persona_agent_response(
                        instruction, plan_steps=plan_steps, current_step_index=i
                    ):
                        yield message_dict
                        if message_dict.get("type") == "agent_stream_chunk" and message_dict.get("agent") == "✨ Persona Agent":
                            persona_agent_full_text += message_dict.get("content", "")
                    step_output_data = persona_agent_full_text

                elif agent_name_from_plan == "MainCoder":
                    art_guidance_for_coder = None
                    if isinstance(previous_step_output, str) and \
                       ("artistic guidance" in previous_step_output.lower() or \
                        "art style" in previous_step_output.lower() or \
                        "mood and tone" in previous_step_output.lower()):
                        art_guidance_for_coder = previous_step_output

                    current_instruction_for_coder = instruction
                    if isinstance(previous_step_output, list) and previous_step_output and \
                       isinstance(previous_step_output[0], dict) and "critique_text" in previous_step_output[0] and \
                       "{ART_CRITIC_FEEDBACK_PLACEHOLDER}" in current_instruction_for_coder:
                        critique_text_to_inject = "".join(
                            f"Critique for '{art_crit_item.get('image_path', 'image')}':\n{art_crit_item['critique_text']}\n\n"
                            for art_crit_item in previous_step_output if art_crit_item.get("critique_text")
                        )
                        if critique_text_to_inject:
                            current_instruction_for_coder = current_instruction_for_coder.replace("{ART_CRITIC_FEEDBACK_PLACEHOLDER}", critique_text_to_inject.strip())
                            yield {"type": "system", "content": "📝 Injected ArtCritic feedback into MainCoder instruction for refinement."}

                    main_coder_output_dict = yield from self._execute_main_coder_phase(
                        coder_instruction=current_instruction_for_coder,
                        art_guidance=art_guidance_for_coder
                    )
                    step_output_data = main_coder_output_dict

                    # Check for re-plan request from MainCoder
                    if isinstance(step_output_data, dict) and "text_response" in step_output_data:
                        response_text = step_output_data["text_response"]
                        lines = response_text.strip().splitlines()
                        if lines and lines[-1].startswith("REQUEST_REPLAN:"):
                            replan_requested = True
                            replan_reason = lines[-1][len("REQUEST_REPLAN:"):].strip()
                            step_output_data["text_response"] = "\n".join(lines[:-1]).strip() # Remove directive from output
                            # Also update implementation_results if any command output this as part of its string.
                            # This is less likely as commands return structured data.
                            # For now, assume it's primarily in the raw text_response.

                elif agent_name_from_plan == "CodeCritic":
                    if isinstance(previous_step_output, dict) and "text_response" in previous_step_output:
                        step_output_data = yield from self._get_code_critique_results(
                            original_user_prompt, previous_step_output, instruction
                        )
                    else:
                        yield {"type": "error", "content": "CodeCritic called without valid MainCoder output from previous step."}
                        step_output_data = {"error": "Missing valid input for CodeCritic."}

                elif agent_name_from_plan == "ArtCritic":
                    if isinstance(previous_step_output, dict):
                        images_to_critique = previous_step_output.get("generated_image_paths", [])
                        step_output_data = yield from self._get_art_critique_results(
                            original_user_prompt, previous_step_output, instruction, images_to_critique
                        )
                    else:
                        yield {"type": "error", "content": "ArtCritic called without valid MainCoder output from previous step."}
                        step_output_data = {"error": "Missing valid input for ArtCritic."}
                
                else:
                    yield {"type": "error", "content": f"Unknown agent in plan: {agent_name_from_plan}. Skipping step."}
                    step_output_data = f"Error: Unknown agent {agent_name_from_plan}"

                # --- Re-plan logic ---
                if replan_requested:
                    yield {"type": "system", "content": f"🤖 Agent {agent_name_from_plan} requested a re-plan. Reason: {replan_reason}. Initiating new planning cycle..."}

                    # Summarize recent changes for the new planner prompt
                    recent_changes_summary = "No recent changes logged."
                    if hasattr(self, 'project_context') and self.project_context.get("recent_changes"):
                        changes_to_log = self.project_context["recent_changes"][-5:] # Last 5 changes for context
                        formatted_changes = [f"- {ch['command']}: {str(ch['args'])[:100]}" for ch in changes_to_log]
                        if formatted_changes:
                            recent_changes_summary = "\n".join(formatted_changes)

                    new_planner_prompt = (
                        f"RE-PLANNING REQUESTED. Original User Prompt: '{original_user_prompt}'.\n"
                        f"Reason for Re-plan by {agent_name_from_plan}: '{replan_reason}'.\n"
                        f"Context of recent system actions that led to this:\n{recent_changes_summary}\n\n"
                        f"Please formulate a new plan to achieve the original user prompt, taking this new context and reason into account. Avoid the previous pitfalls."
                    )

                    new_plan_steps = self._get_plan_from_planner(new_planner_prompt)
                    if new_plan_steps:
                        plan_steps = new_plan_steps
                        i = -1 # Reset loop to start from the beginning of the new plan
                        previous_step_output = None # Reset previous output
                        yield {"type": "system", "content": f"📜 New plan received with {len(plan_steps)} steps. Restarting execution..."}
                        if agent_name_for_status not in ["unknown_agent", "planner_agent_direct", "persona_agent"]:
                             yield {"type": "agent_status_update", "agent": agent_name_for_status, "status": "inactive"} # Current agent inactive
                        continue # Restart the loop with the new plan
                    else:
                        yield {"type": "error", "content": "Planner failed to generate a new plan after re-plan request. Stopping."}
                        break # Exit the loop

                if agent_name_for_status not in ["unknown_agent", "planner_agent_direct", "persona_agent"]:
                    yield {"type": "agent_status_update", "agent": agent_name_for_status, "status": "inactive"}

                previous_step_output = step_output_data

                if is_final_step and not replan_requested: # Only consider final if no re-plan is pending
                    yield {"type": "system", "content": f"✅ Final step ({agent_name_from_plan}) completed."}

            except Exception as e:
                if agent_name_for_status not in ["unknown_agent", "planner_agent_direct", "persona_agent"]: # Ensure status is reset on error
                    yield {"type": "agent_status_update", "agent": agent_name_for_status, "status": "inactive"}
                error_msg = f"Error during step execution ({agent_name_from_plan}): {type(e).__name__} - {str(e)}\nFull Traceback:\n{traceback.format_exc()}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": error_msg}
                previous_step_output = {"error": error_msg}
                # Optionally, break the loop:
                # yield {"type": "system", "content": f"Stopping plan execution due to error in step {i+1}."}
                # break

        yield {"type": "system", "content": "🏁 Planner execution complete."}


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
            try:
                rel_target_image_path = Path(target_image_path).relative_to(VM_DIR)
            except ValueError:
                rel_target_image_path = target_image_path

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
            yield f"Error generating art critique: {e}"

    def _get_proactive_art_guidance(self, current_user_prompt):
        """Get proactive art guidance before image generation."""
        try:
            context_text = f"USER REQUEST FOR NEW IMAGE:\n{current_user_prompt}"
            formatted_proactive_prompt = PROACTIVE_ART_AGENT_PROMPT.replace("{{USER_REQUEST}}", current_user_prompt)
            proactive_art_context_parts = self._build_visual_context(
                context_text=context_text,
                system_prompt=formatted_proactive_prompt
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
            self._log_interaction("proactive_art_critic", full_response_text)
        except Exception as e:
            self.error_context.append(f"Proactive Art Critic Error: {e}")
            yield f"Error generating proactive art guidance: {e}"


    def _move_to_trash(self, image_paths_to_move):
        """Moves specified image paths to the .trash directory within VM_DIR."""
        messages = []
        trash_dir = VM_DIR / TRASH_DIR_NAME
        try:
            trash_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messages.append(f"❌ Error creating trash directory {trash_dir}: {e}")
            return messages

        for img_path_str in image_paths_to_move:
            try:
                source_path = Path(img_path_str)
                if not source_path.is_absolute() and not str(source_path).startswith(str(VM_DIR)):
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
            except Exception as e:
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
        """Update project context for better agent awareness, using caching."""
        if self.project_files_changed or self.project_files_cache is None:
            self.file_snippet_cache.clear()
            current_files = self._scan_project_files()
            current_images = self._scan_project_images()
            self.project_files_cache = {
                "files": current_files,
                "images": current_images,
                "timestamp": time.time()
            }
            self.project_files_changed = False
            existing_recent_changes = self.project_context.get("recent_changes", [])
            self.project_context = {
                "files": current_files,
                "images": current_images,
                "recent_changes": existing_recent_changes
            }
        else:
            self.project_context["files"] = self.project_files_cache["files"]
            self.project_context["images"] = self.project_files_cache["images"]
            if "recent_changes" not in self.project_context:
                 self.project_context["recent_changes"] = []

    def _build_enhanced_prompt(self, user_prompt, system_prompt, proactive_art_advice=None, current_plan_summary: str | None = None, project_files_summary: str | None = None, recent_changes_summary: str | None = None, error_log_summary: str | None = None):
        """Build enhanced prompt with comprehensive context"""
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        base_context_text = f"{system_prompt}\n\n**CURRENT TIME:**\n{current_time_str}\n\n"

        if hasattr(self, 'user_preferences') and self.user_preferences:
            preferences_text = "\n".join([f"- {key}: {value}" for key, value in self.user_preferences.items()])
            base_context_text += f"**USER PREFERENCES:** (These are read-only in this view. Use commands to set/get specific preferences during tasks.)\n{preferences_text}\n\n"

        if recent_changes_summary:
            base_context_text += f"**RECENT SYSTEM ACTIONS (LOG):**\n{recent_changes_summary}\n\n"
        if error_log_summary:
            base_context_text += f"**RECENT ERRORS (LOG):**\n{error_log_summary}\n\n"

        if current_plan_summary:
            base_context_text += f"**CURRENT PLAN STATUS:**\n{current_plan_summary}\n\n"

        if project_files_summary:
            base_context_text += f"**PROJECT FILES OVERVIEW:**\n{project_files_summary}\n\n"

        base_context_text += "**PROJECT STATUS:**\n" # This will be followed by file listings etc.

        prompt_parts = [{"text": base_context_text}]

        if proactive_art_advice: # This should be appended after the main text block, or integrated if preferred
            # For now, appending as a separate part if it exists, to maintain its distinct section.
            # Or, it could be integrated into base_context_text before PROJECT STATUS if that's more logical.
            # Let's try integrating it before project status for better flow.
            # Re-evaluation: The original placement for proactive_art_advice was as a separate append if present.
            # Let's stick to modifying the initial text part for preferences and keep proactive_art_advice logic separate for now.
            # The current diff will modify prompt_parts[0] and then append proactive_art_advice if it exists.
             prompt_parts.append({"text": f"\n**PROACTIVE ART GUIDANCE:**\n{proactive_art_advice}\n"})

        if VM_DIR.exists():
            for root, dirs, files in os.walk(VM_DIR):
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
                            content_snippet = ""
                            try:
                                current_mtime = os.path.getmtime(file_path)
                                if rel_path in self.file_snippet_cache:
                                    cached_mtime, cached_snippet = self.file_snippet_cache[rel_path]
                                    if current_mtime == cached_mtime:
                                        content_snippet = cached_snippet
                                else:
                                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                        content_snippet = f.read(3000)
                                    self.file_snippet_cache[rel_path] = (current_mtime, content_snippet)
                            except OSError:
                                content_snippet = "[Error reading file content]"
                            prompt_parts.append({"text": f"\n--- FILE: {rel_path} ---\n{content_snippet}\n"})
                    except IOError:
                        prompt_parts.append({"text": f"\n--- FILE/IMAGE ERROR (IOError): {rel_path} ---\n"})
                        continue
        if self.conversation_history:
            prompt_parts.append({"text": "\n**CONVERSATION HISTORY:**\n"})
            for entry in self.conversation_history[-8:]:
                role = entry["role"].replace("_", " ").title()
                content = entry["content"][:300] + "..." if len(entry["content"]) > 300 else entry["content"]
                prompt_parts.append({"text": f"{role}: {content}\n\n"})
        if self.error_context:
            prompt_parts.append({"text": f"\n**RECENT ERRORS:**\n{chr(10).join(self.error_context[-3:])}\n"})
        prompt_parts.append({"text": f"\n**USER REQUEST:**\n{user_prompt}"})
        return prompt_parts

    def _execute_persona_agent_response(self, instruction: str, plan_steps: list | None = None, current_step_index: int | None = None):
        self._update_project_context() # Ensure project context is fresh
        yield {"type": "system", "content": f"💬 Persona Agent responding to: {instruction}"}

        # Gather Project Files Summary
        files_summary_str = "No file data available."
        if hasattr(self, 'project_context'):
            all_files = self.project_context.get("files", [])
            all_images = self.project_context.get("images", [])

            file_count = len(all_files)
            image_count = len(all_images)

            py_files = len([f for f in all_files if f.endswith('.py')])
            txt_files = len([f for f in all_files if f.endswith('.txt')])
            # Add more extensions as needed or a generic counter for other code files
            other_code_files = len([f for f in all_files if not f.endswith(('.py', '.txt')) and '.' in f])


            files_summary_str = f"Project Overview: {file_count} code/text file(s) (e.g., {py_files} Python, {txt_files} text, {other_code_files} other), {image_count} image(s)."

        # Gather Recent Changes Summary
        recent_changes_summary_str = "No recent changes logged."
        if hasattr(self, 'project_context') and self.project_context.get("recent_changes"):
            changes_to_show = self.project_context["recent_changes"][-3:] # Last 3 changes
            formatted_changes = []
            for change in changes_to_show:
                formatted_changes.append(f"- {change.get('command')}: {str(change.get('args'))[:100]}")
            if formatted_changes:
                recent_changes_summary_str = "Last few system actions:\n" + "\n".join(formatted_changes)

        # Gather Error Log Summary
        error_log_summary_str = "No recent errors logged."
        if self.error_context:
            errors_to_show = self.error_context[-2:] # Last 2 errors
            formatted_errors = [f"- {str(err)[:150]}" for err in errors_to_show]
            if formatted_errors:
                error_log_summary_str = f"Recent system errors ({len(self.error_context)} total):\n" + "\n".join(formatted_errors)

        plan_summary_for_persona = None
        if plan_steps and current_step_index is not None:
            num_total_steps = len(plan_steps)
            current_step_details = plan_steps[current_step_index]
            summary_lines = [
                f"I am currently executing a plan with {num_total_steps} step(s).",
                f"We are on step {current_step_index + 1} of {num_total_steps}: Agent '{current_step_details.get('agent_name')}' is tasked with: '{str(current_step_details.get('instruction','N/A'))[:100]}{'...' if len(str(current_step_details.get('instruction','N/A'))) > 100 else ''}'."
            ]
            if current_step_index + 1 < num_total_steps:
                next_step_details = plan_steps[current_step_index + 1]
                summary_lines.append(f"The next step involves agent '{next_step_details.get('agent_name')}' to work on: '{str(next_step_details.get('instruction','N/A'))[:100]}{'...' if len(str(next_step_details.get('instruction','N/A'))) > 100 else ''}'.")
            else:
                summary_lines.append("This is the final step in the current plan.")
            plan_summary_for_persona = "\n".join(summary_lines)

        persona_prompt_parts = self._build_enhanced_prompt(
            user_prompt=instruction,
            system_prompt=PERSONA_AGENT_PROMPT,
            current_plan_summary=plan_summary_for_persona,
            project_files_summary=files_summary_str,
            recent_changes_summary=recent_changes_summary_str,
            error_log_summary=error_log_summary_str
        )

        self._log_interaction("persona_agent_input_instruction", instruction)

        full_response_text = ""
        try:
            response_stream = self.client.models.generate_content_stream(
                model=TEXT_MODEL_NAME, # Assuming TEXT_MODEL_NAME is appropriate
                contents=persona_prompt_parts
            )
            for chunk in response_stream:
                if chunk.text:
                    full_response_text += chunk.text
                    yield {"type": "agent_stream_chunk", "agent": "✨ Persona Agent", "content": chunk.text}

            self._log_interaction("persona_agent_full_response", full_response_text)

        except Exception as e:
            error_msg = f"Persona Agent LLM Error: {e}"
            self.error_context.append(error_msg)
            self._log_interaction("persona_agent_error", error_msg)
            yield {"type": "error", "content": error_msg}
            # Optionally, yield a fallback message from Persona Agent if LLM fails
            yield {"type": "agent_stream_chunk", "agent": "✨ Persona Agent", "content": "I encountered an issue trying to process that. Please try again."}

    def _build_visual_context(self, context_text, system_prompt):
        """Build visual context for art critic with all images"""
        context_parts = [{"text": f"{system_prompt}\n\n{context_text}\n\n**VISUAL CONTEXT:**\n"}]
        if VM_DIR.exists():
            image_count = 0
            for root, dirs, files in os.walk(VM_DIR):
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
        simple_commands = [
            'run', 'start', 'execute', 'launch', 'install', 'update', 'pip install',
            'npm install', 'serve', 'host', 'deploy', 'build', 'compile'
        ]
        prompt_lower = user_prompt.lower()
        if any(cmd in prompt_lower and len(prompt_lower.split()) <= 4 for cmd in simple_commands):
            return False
        code_creation_indicators = [
            'create_file', 'write_to_file', 'function', 'class', 'algorithm',
            'implement', 'refactor', 'optimize', 'fix bug', 'debug', 'security',
            'performance', 'review code', 'analyze code'
        ]
        text_to_check = f"{user_prompt} {main_response}".lower()
        has_code_work = any(indicator in text_to_check for indicator in code_creation_indicators)
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
        simple_commands = [
            'run', 'start', 'execute', 'launch', 'install', 'update', 'serve'
        ]
        explicit_visual_analysis = any(phrase in prompt_lower for phrase in [
            'analyze image', 'review design', 'visual feedback', 'art critique',
            'design review', 'improve visuals'
        ])
        if explicit_visual_analysis:
            return True
        if any(cmd in prompt_lower and len(prompt_lower.split()) <= 4 for cmd in simple_commands):
            if not any(vis_cmd in prompt_lower for vis_cmd in ['image', 'visual', 'art', 'design', 'graphic']):
                return False
        visual_work_indicators = [
            'generate_image', 'create image', 'design', 'visual', 'ui', 'interface',
            'color', 'layout', 'style', 'aesthetic', 'art', 'graphic', 'icon',
            'logo', 'banner', 'picture', 'photo'
        ]
        text_to_check = f"{user_prompt} {main_response}".lower()
        has_visual_work = any(indicator in text_to_check for indicator in visual_work_indicators)
        has_image_changes = any(result.get("type") == "file_changed" and 
                               result.get("content", "").lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
                               for result in implementation_results)
        return has_visual_work or has_image_changes

    def _needs_refinement(self, implementation_results):
        """Determine if refinement is needed based on results"""
        error_count = sum(1 for result in implementation_results if result.get("type") == "error")
        complex_operations = sum(1 for result in implementation_results 
                               if result.get("type") == "system" and 
                               any(op in result.get("content", "") for op in ["Created file", "Updated file", "Generated"]))
        return error_count > 0 or complex_operations > 2

    def _has_project_images(self):
        """Check if project contains images, using cached context if available."""
        if self.project_context and "images" in self.project_context:
            if self.project_files_cache and self.project_context["images"] is not None:
                return bool(self.project_context["images"])
        if not VM_DIR.exists():
            return False
        for root, dirs, files in os.walk(VM_DIR):
            if TRASH_DIR_NAME in dirs:
                dirs.remove(TRASH_DIR_NAME)
            for name in files:
                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    return True
        return False

    def _process_enhanced_commands(self, response_text):
        """Enhanced command processing with a more specific regex, pre-checks, and detailed error logging."""
        command_pattern = re.compile(r'`\s*([a-zA-Z_][\w\.]*\s*\(.*?\))\s*`', re.DOTALL)
        matches = command_pattern.finditer(response_text)
        for match in matches:
            command_str = match.group(1).strip()
            if not command_str:
                continue
            if not any(command_str.startswith(known_cmd + "(") for known_cmd in self.command_handlers.keys()):
                yield {"type": "system", "content": f"ℹ️ Note: Ignoring potential command-like text: `{command_str[:100]}{'...' if len(command_str) > 100 else ''}`"}
                continue
            try:
                parsed_expr = ast.parse(command_str, mode="eval")
                call_node = parsed_expr.body
                if not isinstance(call_node, ast.Call):
                    self.error_context.append(f"Command parsing error: Not a function call - '{command_str}'")
                    yield {"type": "error", "content": f"❌ Command error: Not a function call - `{command_str}`"}
                    continue
                func_name = call_node.func.id
                if func_name not in self.command_handlers:
                    self.error_context.append(f"Unknown command: '{func_name}' in '{command_str}'")
                    yield {"type": "error", "content": f"❌ Unknown command: `{func_name}`"}
                    continue
                args = []
                for arg_node in call_node.args:
                    try:
                        args.append(ast.literal_eval(arg_node))
                    except ValueError as ve:
                        error_msg = f"Command argument error: Non-literal argument in '{command_str}'. Argument: {ast.dump(arg_node)}. Error: {ve}"
                        self.error_context.append(error_msg)
                        yield {"type": "error", "content": f"❌ Command error: Invalid argument in `{command_str}`"}
                        break
                else:
                    result = self.command_handlers[func_name](*args)
                    if func_name == "generate_image":
                        for update in result:
                            yield update
                    else:
                        yield {"type": "system", "content": result}
                        if "✅" in result:
                            if func_name == "create_file" and args:
                                yield {"type": "file_changed", "content": args[0]}
                            elif func_name == "write_to_file" and args:
                                yield {"type": "file_changed", "content": args[0]}
                            elif func_name == "delete_file" and args:
                                yield {"type": "file_changed", "content": args[0]}
                            elif func_name == "rename_file" and len(args) > 1:
                                yield {"type": "file_changed", "content": args[1]}
                    if func_name in ["create_file", "write_to_file", "generate_image", "delete_file", "rename_file"]:
                        if "recent_changes" not in self.project_context:
                            self.project_context["recent_changes"] = []
                        self.project_context["recent_changes"].append({
                            "command": func_name,
                            "args": args,
                            "timestamp": time.time()
                        })
                        self.project_context["recent_changes"] = self.project_context["recent_changes"][-20:]
                        self.project_files_changed = True
                    continue
                if args and isinstance(args[-1], Exception):
                     continue
            except SyntaxError as se:
                error_msg = f"Command syntax error: Unable to parse '{command_str}'. Error: {se}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": f"❌ Command syntax error: `{command_str}`"}
            except ValueError as ve:
                error_msg = f"Command value error: Problem with argument values in '{command_str}'. Error: {ve}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": f"❌ Command value error: `{command_str}`"}
            except Exception as e:
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
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-15:]

    def _format_results(self, results):
        """Formats a list of implementation results for inclusion in agent prompts."""
        if not results:
            return "No implementation results"
        formatted = []
        for result in results[-5:]:
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

    def _scan_project_files(self):
        """Scans and returns a list of project files (non-images). Internal use for cache building."""
        files = []
        if VM_DIR.exists():
            for root, dirs, filenames in os.walk(VM_DIR):
                if TRASH_DIR_NAME in dirs:
                    dirs.remove(TRASH_DIR_NAME)
                for name in filenames:
                    if not name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                        files.append(rel_path)
        return files

    def _scan_project_images(self):
        """Scans and returns a list of project images. Internal use for cache building."""
        images = []
        if VM_DIR.exists():
            for root, dirs, filenames in os.walk(VM_DIR):
                if TRASH_DIR_NAME in dirs:
                    dirs.remove(TRASH_DIR_NAME)
                for name in filenames:
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                        images.append(rel_path)
        return images

    def _get_project_files(self):
        """Get list of project files from context (populated by _update_project_context)."""
        return self.project_context.get("files", [])

    def _get_project_images(self):
        """Get list of project images from context (populated by _update_project_context)."""
        return self.project_context.get("images", [])

    def _get_recent_changes(self):
        """Get recent project changes from context (populated by _process_enhanced_commands)."""
        return self.project_context.get("recent_changes", [])

    def _extract_grade(self, agent_response):
        """Extract numerical grade from agent response"""
        if not agent_response:
            return None
        grade_match = re.search(r'GRADE:\s*(\d+)/100', agent_response, re.IGNORECASE)
        if grade_match:
            return int(grade_match.group(1))
        grade_match = re.search(r'\bgrade[:\s]*(\d{1,3})\b', agent_response, re.IGNORECASE)
        if grade_match:
            return int(grade_match.group(1))
        return None

    def _calculate_overall_grade(self, critic_grade, art_grade):
        """Calculate overall grade from individual agent grades"""
        grades = [g for g in [critic_grade, art_grade] if g is not None]
        if not grades:
            return 85
        return sum(grades) // len(grades)

    def _safe_path(self, filename):
        """Sanitize file paths to ensure they are within VM_DIR and prevent traversal."""
        if not filename:
            return None
        if Path(filename).is_absolute():
            return None
        abs_vm_dir = os.path.abspath(VM_DIR)
        full_path = VM_DIR / filename
        abs_full_path = os.path.abspath(full_path)
        if os.path.commonprefix([abs_full_path, abs_vm_dir]) != abs_vm_dir:
            return None
        return full_path

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
            import shlex
            cmd_parts = shlex.split(command)
            if not cmd_parts:
                return "❌ Empty command provided"
            proc = subprocess.run(
                cmd_parts,
                cwd=VM_DIR,
                shell=False,
                capture_output=True,
                text=True,
                timeout=120
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

        self.bg_color_dark = "#2E2E2E"
        self.fg_color_light = "#F0F0F0"
        self.bg_color_medium = "#3C3C3C"
        self.border_color = "#505050"
        self.accent_color = "#007ACC"

        self.user_chat_color = "#7FFFD4"
        self.system_chat_color = "#4DB6AC"
        self.timestamp_chat_color = "#B0B0B0"
        self.error_chat_color = "#FF8A80"

        self.agent_status_inactive_color = "#66BB6A"
        self.agent_status_active_color = "#FFA726"
        self.agent_status_error_color = "#EF5350"

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.configure(bg=self.bg_color_dark)

        self.style.configure("TFrame", background=self.bg_color_dark)
        self.style.configure(
            "TLabelframe",
            background=self.bg_color_dark,
            bordercolor=self.border_color,
            relief=tk.SOLID,
            borderwidth=1
        )
        self.style.configure(
            "TLabelframe.Label",
            background=self.bg_color_dark,
            foreground=self.fg_color_light,
            padding=(5, 2)
        )
        self.style.configure("TPanedwindow", background=self.bg_color_dark)
        self.style.configure("Sash", background=self.bg_color_medium, bordercolor=self.border_color, relief=tk.RAISED, sashthickness=6)

        self.style.configure("Vertical.TScrollbar", background=self.bg_color_medium, troughcolor=self.bg_color_dark, bordercolor=self.border_color, arrowcolor=self.fg_color_light, relief=tk.FLAT, arrowsize=12)
        self.style.configure("Horizontal.TScrollbar", background=self.bg_color_medium, troughcolor=self.bg_color_dark, bordercolor=self.border_color, arrowcolor=self.fg_color_light, relief=tk.FLAT, arrowsize=12)
        self.style.map("TScrollbar",
            background=[('active', self.accent_color), ('!active', self.bg_color_medium)],
            arrowcolor=[('pressed', self.accent_color), ('!pressed', self.fg_color_light)]
        )

        self.style.configure("TButton", background=self.accent_color, foreground="white", padding=(8, 4), font=('Segoe UI', 9, 'bold'), borderwidth=1, relief=tk.RAISED, bordercolor=self.accent_color)
        self.style.map("TButton",
                       background=[('active', '#005f9e'), ('pressed', '#004c8c'), ('disabled', self.bg_color_medium)],
                       foreground=[('disabled', self.border_color)],
                       relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)])

        self.style.configure("Treeview", background=self.bg_color_medium, foreground=self.fg_color_light, fieldbackground=self.bg_color_medium, rowheight=22, borderwidth=1, relief=tk.SOLID, bordercolor=self.border_color)
        self.style.map("Treeview",
                       background=[('selected', self.accent_color)],
                       foreground=[('selected', "white")])
        self.style.configure("Treeview.Heading", background=self.bg_color_dark, foreground=self.fg_color_light, relief=tk.FLAT, padding=(5, 5), font=('Segoe UI', 9, 'bold'), borderwidth=0)
        self.style.map("Treeview.Heading",
                       background=[('active', self.bg_color_medium)],
                       relief=[('active', tk.GROOVE), ('!active', tk.FLAT)])

        self.style.configure("TNotebook", background=self.bg_color_dark, tabmargins=(5, 5, 5, 0), borderwidth=1, bordercolor=self.border_color)
        self.style.configure("TNotebook.Tab", background=self.bg_color_medium, foreground=self.fg_color_light, padding=(8,4), font=('Segoe UI', 9), borderwidth=0, relief=tk.FLAT)
        self.style.map("TNotebook.Tab",
                       background=[("selected", self.accent_color), ("active", self.bg_color_dark)],
                       foreground=[("selected", "white"), ("active", self.fg_color_light)],
                       relief=[("selected", tk.FLAT), ("!selected", tk.FLAT)],
                       borderwidth=[("selected",0)])

        self.style.configure("TLabel", background=self.bg_color_dark, foreground=self.fg_color_light, padding=2)
        self.style.configure("Status.TLabel", background=self.bg_color_dark, foreground=self.fg_color_light, padding=5, relief=tk.FLAT)


        VM_DIR.mkdir(exist_ok=True)
        self.msg_queue = queue.Queue()
        self.current_image = None
        self.current_open_file_path = None

        self.file_tree_cache = {}
        self.file_tree_cache_dirty = True
        self.chat_chunk_color_tags = {}

        self._debounce_refresh_id = None
        self._debounce_insights_id = None
        self._save_timer = None
        self._debounce_interval = 300

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
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📄 New File", command=self.new_file)
        file_menu.add_command(label="💾 Save File", command=self.save_current_file)
        file_menu.add_command(label="🔄 Refresh Files", command=self.refresh_files)
        file_menu.add_separator()
        file_menu.add_command(label="🧹 Clear Chat", command=self.clear_chat)
        file_menu.add_command(label="📊 Project Stats", command=self.show_project_stats)
        menubar.add_cascade(label="File", menu=file_menu)
        agents_menu = tk.Menu(menubar, tearoff=0)
        agents_menu.add_command(label="🤖 Test Main Coder", command=lambda: self.test_agent("main"))
        agents_menu.add_command(label="📊 Test Code Critic", command=lambda: self.test_agent("critic"))
        agents_menu.add_command(label="🎨 Test Art Critic", command=lambda: self.test_agent("art"))
        agents_menu.add_separator()
        agents_menu.add_command(label="🔄 Reset Agent Memory", command=self.reset_agent_memory)
        menubar.add_cascade(label="Agents", menu=agents_menu)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="🔑 Set API Key", command=self.prompt_api_key)
        settings_menu.add_command(label="⚙️ Agent Settings", command=self.show_agent_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        menubar.config(bg=self.bg_color_dark, fg=self.fg_color_light, activebackground=self.accent_color, activeforeground="white", relief=tk.FLAT, borderwidth=0)
        for menu_item in [file_menu, agents_menu, settings_menu]:
            menu_item.config(bg=self.bg_color_medium, fg=self.fg_color_light, activebackground=self.accent_color, activeforeground="white", relief=tk.FLAT, borderwidth=0)
        self.config(menu=menubar)

    def _setup_left_panel(self, parent_pane):
        """Sets up the left panel with image preview and file tree."""
        left_frame = ttk.Frame(parent_pane)
        parent_pane.add(left_frame, weight=1)
        img_frame = ttk.LabelFrame(left_frame, text="🖼️ Visual Preview", padding=5)
        img_frame.pack(fill=tk.X, pady=(0, 5))
        self.canvas = tk.Canvas(img_frame, bg=self.bg_color_medium, height=320, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(160, 160, text="🖼️ No image selected\nImages will be analyzed by Art Critic",
                               fill=self.fg_color_light, font=("Arial", 11), justify=tk.CENTER)
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
        editor_frame = ttk.Frame(self.notebook)
        self.editor = scrolledtext.ScrolledText(
            editor_frame, wrap=tk.WORD, font=("Consolas", 12), padx=15, pady=15,
            bg=self.bg_color_medium, fg=self.fg_color_light, insertbackground=self.fg_color_light,
            relief=tk.FLAT, borderwidth=0, highlightthickness=1, highlightbackground=self.border_color
        )
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.frame.config(background=self.bg_color_dark)
        self.notebook.add(editor_frame, text="📝 Code Editor")
        chat_frame = ttk.Frame(self.notebook)
        self.chat = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, font=("Segoe UI", 11), padx=15, pady=15, state="disabled",
            bg=self.bg_color_medium, fg=self.fg_color_light, insertbackground=self.fg_color_light,
            relief=tk.FLAT, borderwidth=0, highlightthickness=1, highlightbackground=self.border_color
        )
        self.chat.pack(fill=tk.BOTH, expand=True)
        self.chat.frame.config(background=self.bg_color_dark)
        self.notebook.add(chat_frame, text="🤖 Multi-Agent Chat")
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
        right_frame = self._setup_right_panel(main_pane)
        self._setup_input_area(right_frame)
        self.editor.bind("<Control-s>", lambda e: self.save_current_file())
        self._setup_enhanced_syntax_highlighting()
        self.editor.bind("<KeyRelease>", self._on_editor_key_release)
        self._schedule_refresh_files()

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
        self.editor.tag_configure("keyword", foreground="#569cd6")
        self.editor.tag_configure("string", foreground="#ce9178")
        self.editor.tag_configure("comment", foreground="#6a9955")
        self.editor.tag_configure("number", foreground="#b5cea8")
        self.editor.tag_configure("function", foreground="#dcdcaa")
        self.editor.tag_configure("class", foreground="#4ec9b0")
        self.editor.tag_configure("operator", foreground="#d4d4d4")
        raw_patterns = {
            "keyword": r"\b(def|class|import|from|for|while|if|elif|else|return|in|and|or|not|is|with|as|try|except|finally|raise|yield|pass|continue|break|global|nonlocal|lambda|assert|async|await)\b",
            "string": r"(\".*?\"|\'.*?\'|\"\"\".*?\"\"\"|\'\'\'.*?\'\'\')",
            "comment": r"#.*",
            "number": r"\b\d+(\.\d*)?\b",
            "function": r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()",
            "class": r"\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            "operator": r"[+\-*/=<>!&|^~%]"
        }
        self.compiled_syntax_patterns = {
            tag: re.compile(pattern, re.MULTILINE | re.DOTALL)
            for tag, pattern in raw_patterns.items()
        }

    def _apply_full_syntax_highlighting(self):
        """Apply full syntax highlighting to the entire document."""
        content = self.editor.get("1.0", tk.END)
        for tag in self.compiled_syntax_patterns.keys():
            self.editor.tag_remove(tag, "1.0", tk.END)
        for tag, compiled_pattern in self.compiled_syntax_patterns.items():
            for match in compiled_pattern.finditer(content):
                start, end = match.span()
                self.editor.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

    def _apply_optimized_syntax_highlighting(self, event=None):
        """Apply syntax highlighting only to a range of lines around the edit."""
        try:
            current_pos = self.editor.index(tk.INSERT)
            current_line = int(current_pos.split('.')[0])
            start_line = max(1, current_line - 5)
            last_doc_line_str = self.editor.index(f"{tk.END}-1c").split('.')[0]
            last_doc_line = int(last_doc_line_str) if last_doc_line_str.isdigit() else 1
            end_line = min(last_doc_line, current_line + 5)
            if start_line > end_line:
                start_line = end_line
            start_index = f"{start_line}.0"
            end_index = f"{end_line}.end"
            content_to_highlight = self.editor.get(start_index, end_index)
            if not content_to_highlight:
                return
            for tag_key in self.compiled_syntax_patterns.keys():
                self.editor.tag_remove(tag_key, start_index, end_index)
            for tag_key, compiled_pattern in self.compiled_syntax_patterns.items():
                for match in compiled_pattern.finditer(content_to_highlight):
                    match_start_offset, match_end_offset = match.span()
                    abs_match_start = self.editor.index(f"{start_index} + {match_start_offset} chars")
                    abs_match_end = self.editor.index(f"{start_index} + {match_end_offset} chars")
                    self.editor.tag_add(tag_key, abs_match_start, abs_match_end)
        except Exception:
            self._apply_full_syntax_highlighting()
            pass

    def _on_editor_key_release(self, event=None):
        """Enhanced editor key release handler"""
        self._apply_optimized_syntax_highlighting()
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
            style="Status.TLabel",
            anchor=tk.W
        )
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.agent_status_frame = ttk.Frame(status_frame)
        self.agent_status_frame.pack(side=tk.RIGHT, padx=5)
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
            self._draw_enhancer_toggle_switch()
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
        file_count = len(self.agent_system._get_project_files())
        image_count = len(self.agent_system._get_project_images())
        insights.append(f"📁 Files: {file_count}")
        insights.append(f"🖼️ Images: {image_count}")
        recent_changes = len(self.agent_system._get_recent_changes())
        insights.append(f"🔄 Recent changes: {recent_changes}")
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
        self.add_chat_message("👤 You", text, color=self.user_chat_color)
        self.input_txt.delete("1.0", tk.END)
        self.input_txt.config(state="disabled")
        self.send_btn.config(state="disabled")
        self.screenshot_btn.config(state="disabled")
        self.status_var.set("🔄 Enhanced Multi-Agent System Processing...")
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
        """Enhanced file tree refresh with metadata, using caching."""
        self.tree.delete(*self.tree.get_children())
        if self.file_tree_cache_dirty:
            self.file_tree_cache.clear()
            self._rebuild_file_tree_cache(VM_DIR, self.file_tree_cache)
            self.file_tree_cache_dirty = False
        self._populate_tree_from_cache("", self.file_tree_cache)

    def _rebuild_file_tree_cache(self, current_path_obj, current_cache_level):
        """Recursively builds the file tree cache."""
        try:
            for item in sorted(current_path_obj.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
                if item.name == TRASH_DIR_NAME:
                    continue
                rel_path_str = str(item.relative_to(VM_DIR))
                try:
                    stat_info = item.stat()
                    is_dir = item.is_dir()
                    current_cache_level[rel_path_str] = {
                        'name': item.name,
                        'is_dir': is_dir,
                        'size': stat_info.st_size,
                        'children': {}
                    }
                    if is_dir:
                        self._rebuild_file_tree_cache(item, current_cache_level[rel_path_str]['children'])
                except OSError as e:
                    print(f"OSError when processing {item}: {e}")
                    continue
        except OSError as e:
            print(f"OSError when iterating {current_path_obj}: {e}")

    def _populate_tree_from_cache(self, parent_tree_id, cache_node_data):
        """Populates the ttk.Treeview from the cached file structure."""
        sorted_item_keys = sorted(cache_node_data.keys(),
                                  key=lambda k: (not cache_node_data[k]['is_dir'], cache_node_data[k]['name'].lower()))
        for rel_path_str in sorted_item_keys:
            item_data = cache_node_data[rel_path_str]
            item_name = item_data['name']
            if item_data['is_dir']:
                node = self.tree.insert(
                    parent_tree_id,
                    'end',
                    text=f"📁 {item_name}",
                    values=(rel_path_str, ""),
                    open=False
                )
                self._populate_tree_from_cache(node, item_data['children'])
            else:
                size_str = self._format_file_size(item_data['size'])
                name_path = Path(item_name)
                if name_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    icon = "🖼️"
                elif name_path.suffix.lower() in ['.py', '.js', '.html', '.css']:
                    icon = "📝"
                else:
                    icon = "📄"
                self.tree.insert(
                    parent_tree_id,
                    'end',
                    text=f"{icon} {item_name}",
                    values=(rel_path_str, size_str)
                )

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
        timestamp = time.strftime("[%H:%M:%S] ")
        safe_sender_name = re.sub(r'\W+', '', sender)
        sender_tag = f"sender_{safe_sender_name.strip()}"
        self.chat.tag_configure(sender_tag, foreground=color, font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("timestamp", foreground=self.timestamp_chat_color, font=("Segoe UI", 9))
        self.chat.tag_configure("message", font=("Segoe UI", 11))
        self.chat.insert(tk.END, timestamp, "timestamp")
        self.chat.insert(tk.END, f"{sender}:\n", sender_tag)
        self.chat.insert(tk.END, f"{message}\n\n", "message")
        self.chat.see(tk.END)
        self.chat.config(state="disabled")
        self.notebook.select(1)

    def _append_chat_chunk(self, sender, chunk_content, color="#000000"):
        """Appends a chunk of text to the chat, typically from a streaming response."""
        self.chat.config(state="normal")
        current_chat_content = self.chat.get("1.0", tk.END).strip()
        if not current_chat_content.endswith(sender + ":\n"):
            pass
        dynamic_tag_name = f"stream_chunk_{color.lstrip('#')}"
        if dynamic_tag_name not in self.chat_chunk_color_tags:
            self.chat.tag_configure(dynamic_tag_name, foreground=color)
            self.chat_chunk_color_tags[dynamic_tag_name] = True
        self.chat.insert(tk.END, chunk_content, dynamic_tag_name)
        self.chat.see(tk.END)
        self.chat.config(state="disabled")
        if self.notebook.index(self.notebook.select()) != 1:
            self.notebook.select(1)

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
            for f in files[:10]:
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
        settings_window = tk.Toplevel(self)
        settings_window.title("🤖 Agent System Settings")
        settings_window.geometry("500x600")
        settings_window.transient(self)
        settings_window.grab_set()
        main_frame = ttk.Frame(settings_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        title_label = ttk.Label(main_frame, text="🤖 ENHANCED MULTI-AGENT SYSTEM", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        config_frame = ttk.LabelFrame(main_frame, text="📋 Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(config_frame, text=f"• Text Model: {TEXT_MODEL_NAME}").pack(anchor=tk.W)
        ttk.Label(config_frame, text=f"• Image Model: {IMAGE_MODEL_NAME}").pack(anchor=tk.W)
        ttk.Label(config_frame, text="• Vision Capabilities: ✅ Enabled").pack(anchor=tk.W)
        ttk.Label(config_frame, text="• Image Generation: ✅ Enabled").pack(anchor=tk.W)
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
        ttk.Label(grading_frame, text=f"• Max Retry Attempts: {getattr(self.agent_system, 'max_retry_attempts', 3)}").pack(anchor=tk.W)
        ttk.Label(grading_frame, text="• Minimum Passing Grade: 70/100").pack(anchor=tk.W)
        agents_frame = ttk.LabelFrame(main_frame, text="🎯 Agent Capabilities", padding=10)
        agents_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(agents_frame, text="• Main Coder: Implementation + Vision Analysis").pack(anchor=tk.W)
        ttk.Label(agents_frame, text="• Code Critic: Quality + Security + Performance + Grading").pack(anchor=tk.W)
        ttk.Label(agents_frame, text="• Art Critic: Visual Design + UX + Accessibility + Grading").pack(anchor=tk.W)
        memory_frame = ttk.LabelFrame(main_frame, text="💾 Memory Status", padding=10)
        memory_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(memory_frame, text=f"• Conversation History: {len(getattr(self.agent_system, 'conversation_history', []))} entries").pack(anchor=tk.W)
        ttk.Label(memory_frame, text=f"• Error Context: {len(getattr(self.agent_system, 'error_context', []))} entries").pack(anchor=tk.W)
        features_frame = ttk.LabelFrame(main_frame, text="🔧 Features", padding=10)
        features_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(features_frame, text="• Enhanced syntax highlighting").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Auto-save functionality").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Visual file tree with metadata").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Real-time project insights").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Screenshot upload & analysis").pack(anchor=tk.W)
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
            self._draw_enhancer_toggle_switch()

    def _draw_enhancer_toggle_switch(self):
        """Draws the custom toggle switch based on the current state."""
        if not hasattr(self, 'enhancer_toggle_switch') or not hasattr(self, 'agent_system'):
            return
        self.enhancer_toggle_switch.delete("all")
        self.enhancer_toggle_switch.update_idletasks()
        width = self.enhancer_toggle_switch.winfo_width()
        height = self.enhancer_toggle_switch.winfo_height()
        if width <= 1 or height <= 1:
            width = 50
            height = 22
        padding = 2
        oval_diameter = height - 2 * padding
        text_y_offset = height // 2
        if self.agent_system.prompt_enhancer_enabled:
            self.enhancer_toggle_switch.create_rectangle(
                0, 0, width, height,
                fill="#4CAF50", outline="#388E3C", width=1
            )
            self.enhancer_toggle_switch.create_text(
                (width - oval_diameter - padding) / 2, text_y_offset, text="ON", fill="white",
                font=("Segoe UI", 7, "bold"), anchor="center"
            )
            self.enhancer_toggle_switch.create_oval(
                width - oval_diameter - padding, padding,
                width - padding, height - padding,
                fill="white", outline="#BDBDBD"
            )
        else:
            self.enhancer_toggle_switch.create_rectangle(
                0, 0, width, height,
                fill="#F44336", outline="#D32F2F", width=1
            )
            self.enhancer_toggle_switch.create_text(
                (width + oval_diameter + padding) / 2, text_y_offset, text="OFF", fill="white",
                font=("Segoe UI", 7, "bold"), anchor="center"
            )
            self.enhancer_toggle_switch.create_oval(
                padding, padding,
                oval_diameter + padding, height - padding,
                fill="white", outline="#BDBDBD"
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
            self.after(50, self._apply_full_syntax_highlighting)
            self.notebook.select(0)
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
                return
            file_path = self.agent_system._safe_path(file_name)
            if file_path:
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.touch()
                    self.file_tree_cache_dirty = True
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
                self.file_tree_cache_dirty = True
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
                    shutil.rmtree(full_path_to_delete)
                    self.status_var.set(f"✅ Deleted directory: {path_to_delete}")
                else:
                    file_size = full_path_to_delete.stat().st_size
                    full_path_to_delete.unlink()
                    self.status_var.set(f"✅ Deleted file: {path_to_delete} ({self._format_file_size(file_size)})")
                if self.current_open_file_path and self.current_open_file_path == full_path_to_delete:
                    self.editor.delete("1.0", tk.END)
                    self.current_open_file_path = None
                self.file_tree_cache_dirty = True
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
            if messagebox.askyesno("📸 Screenshot Method", 
                                 "Choose screenshot method:\n\n" +
                                 "YES: Auto-capture with Snipping Tool\n" +
                                 "NO: Browse for existing image file"):
                self.status_var.set("📸 Starting screenshot capture...")
                self.screenshot_btn.config(state="disabled", text="📸 Capturing...")
                threading.Thread(target=self._auto_capture_screenshot, daemon=True).start()
            else:
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
            try:
                subprocess.run(["snippingtool", "/clip"], shell=True, timeout=2)
                time.sleep(0.5)
                self._monitor_clipboard_for_screenshot()
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                try:
                    subprocess.run(["snippingtool"], shell=True, timeout=2)
                    time.sleep(0.5)
                    self._monitor_clipboard_for_screenshot()
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
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
        max_wait_time = 30
        check_interval = 0.5
        checks = 0
        max_checks = int(max_wait_time / check_interval)
        self.msg_queue.put({
            "type": "screenshot_info", 
            "content": "Take your screenshot now - it will auto-save when ready..."
        })
        while checks < max_checks:
            try:
                clipboard_image = ImageGrab.grabclipboard()
                if clipboard_image is not None:
                    timestamp = int(time.time())
                    filename = f"screenshot_{timestamp}.png"
                    filepath = VM_DIR / filename
                    clipboard_image.save(filepath, "PNG")
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
        self.msg_queue.put({
            "type": "screenshot_timeout", 
            "content": "Screenshot capture timed out. Please try again or use file browser."
        })

    def _process_uploaded_image(self, file_path):
        """Process uploaded image file"""
        try:
            import shutil
            timestamp = int(time.time())
            original_name = os.path.basename(file_path)
            name_parts = os.path.splitext(original_name)
            filename = f"screenshot_{timestamp}{name_parts[1]}"
            destination = VM_DIR / filename
            shutil.copy2(file_path, destination)
            self._finalize_screenshot_processing(filename)
        except Exception as e:
            messagebox.showerror("❌ Upload Error", f"Failed to process image: {str(e)}")

    def _finalize_screenshot_processing(self, filename):
        """Finalize screenshot processing and add to chat"""
        try:
            self._schedule_refresh_files()
            filepath = VM_DIR / filename
            self.display_enhanced_image(filepath)
            analysis_prompt = f"Please analyze this screenshot '{filename}' and describe what you see, including any UI elements, code, text, or design patterns. Provide detailed feedback and suggestions for improvement."
            self._clear_placeholder(None)
            self.input_txt.delete("1.0", tk.END)
            self.input_txt.insert("1.0", analysis_prompt)
            self.add_chat_message("📸 Auto-Screenshot", f"Screenshot captured and saved as '{filename}' - analysis prompt ready!")
            self.status_var.set(f"✅ Screenshot ready: {filename}")
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
                    # Updated agent_colors to include "✨ Assistant"
                    agent_colors = {
                        "🤖 Main Coder": "#2E8B57",
                        "📊 Code Critic": "#FF6347",
                        "🎭 Art Critic": "#9370DB",
                        "✨ Prompt Enhancer": "#FFD700",
                        "✨ Assistant": "#4DB6AC", # Using system_chat_color for Assistant
                        "🤝 Collaborative": "#4169E1"
                    }
                    color = agent_colors.get(agent_name, self.fg_color_light)
                    self.add_chat_message(agent_name, msg["content"], color)
                elif msg["type"] == "agent_stream_chunk":
                    agent_name = msg["agent"] # This is the display name from the agent method
                    # Colors for streaming chunks by agent's display name
                    stream_chunk_colors = {
                        "🤖 Main Coder": "#2E8B57",
                        "📊 Code Critic": "#FF6347",
                        "🎭 Art Critic": "#9370DB",
                        "🎨 Art Critic (Proactive)": "#9370DB",
                        "✨ Prompt Enhancer": "#FFD700",
                        "✨ Assistant": "#4DB6AC"
                    }
                    color = stream_chunk_colors.get(agent_name, self.fg_color_light)
                    self._append_chat_chunk(agent_name, msg["content"], color)
                elif msg["type"] == "system":
                    self.add_chat_message("🔧 System", msg["content"], color=self.system_chat_color)
                elif msg["type"] == "error":
                    error_content = msg.get("content", "An unspecified error occurred.")
                    self.add_chat_message("❌ Error", error_content, color=self.error_chat_color)
                    self.main_status.config(foreground=self.agent_status_error_color)
                    self.critic_status.config(foreground=self.agent_status_error_color)
                    self.art_status.config(foreground=self.agent_status_error_color)
                    error_summary = str(error_content).split('\n')[0]
                    self.status_var.set(f"❌ Error: {error_summary[:100]}")
                elif msg["type"] == "agent_status_update":
                    agent_name_key = msg["agent"]
                    status = msg["status"]

                    agent_display_names = {
                        "main_coder": "🤖 Main Coder",
                        "code_critic": "📊 Code Critic",
                        "art_critic": "🎨 Art Critic",
                        "art_critic_proactive": "🎨 Art Critic (Proactive)",
                        "prompt_enhancer": "✨ Prompt Enhancer",
                        "planner_agent_direct": "✨ Assistant", # This was for planner's direct response
                        "persona_agent": "✨ Persona Agent"     # New entry
                    }
                    display_name = agent_display_names.get(agent_name_key, agent_name_key.replace("_", " ").title())

                    target_widget = None
                    if agent_name_key in ["main_coder", "prompt_enhancer", "planner_agent_direct", "persona_agent"]:
                        target_widget = self.main_status
                    elif agent_name_key == "code_critic":
                        target_widget = self.critic_status
                    elif agent_name_key == "art_critic" or agent_name_key == "art_critic_proactive":
                        target_widget = self.art_status
                    # No specific status widget for persona_agent yet, can map to main_status or a general one

                    if target_widget:
                        if status == "active":
                            target_widget.config(foreground=self.agent_status_active_color)
                            self.status_var.set(f"{display_name} processing...")
                        elif status == "inactive":
                            target_widget.config(foreground=self.agent_status_inactive_color)
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
                    self.file_tree_cache_dirty = True
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
                    self.main_status.config(foreground=self.agent_status_inactive_color)
                    self.critic_status.config(foreground=self.agent_status_inactive_color)
                    self.art_status.config(foreground=self.agent_status_inactive_color)

        except queue.Empty:
            pass

        self.after(100, self._process_messages)

    def on_close(self):
        """Enhanced close handler, ensures pending 'after' calls are cancelled."""
        if messagebox.askokcancel("🚪 Exit", "Exit Enhanced Multi-Agent IDE?\n\nUnsaved changes will be lost."):
            if self._debounce_refresh_id:
                self.after_cancel(self._debounce_refresh_id)
                self._debounce_refresh_id = None
            if self._debounce_insights_id:
                self.after_cancel(self._debounce_insights_id)
                self._debounce_insights_id = None
            if hasattr(self, '_save_timer') and self._save_timer:
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
