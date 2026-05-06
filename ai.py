from config import GEMINI_API_KEY, GEMINI_ENDPOINT


def generate_prompt(question, options):
    """Generate an enhanced prompt using the Groq prompt generator AI"""
    prompt_generator_prompt = f"""You are a prompt engineer designed to enhance AI answering accuracy.

Given a single multiple-choice question, analyze it and return a custom prompt that helps another AI answer correctly. Your output must help the answering model think logically, avoid common traps, and apply the right reasoning strategy.

Your output must include:

1. **Question Type** (e.g. factual, logic, riddle, math, IQ pattern, geography, history, etc.)
2. **Knowledge Domain** (e.g. mathematics, language, computer science, general knowledge, logic, etc.)
3. **Instructional Prompt**: A concise and effective instruction tailored to the question type and domain. It should:
   - Encourage chain-of-thought reasoning where helpful.
   - Mention common traps to avoid if applicable.
   - Be clear, context-rich, and explainable.
   - Avoid ambiguity and enhance the chance of a correct answer.
   - Explicitly instruct the answering AI to debate, test, and deduct between the remaining options.
4. **Filtered Options**: After careful analysis, eliminate up to 2 obviously wrong options (never more than 2). Return the remaining options in a list as "filtered_options".

Respond in the following JSON format:

{{
  "question_type": "...",
  "domain": "...",
  "instructional_prompt": "...",
  "filtered_options": ["...", "...", ...]
}}

Now, analyze the following question and generate the best instructional prompt:

Question: {question}
Options:
""" + "\n".join(f"- {opt}" for opt in options)
    
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt_generator_prompt
                    }
                ]
            }
        ]
    }
        
    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        print("Prompt Generator (Groq) Response:", result)
        
        result = response.json()
        content = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        
        # Extract all JSON objects using regex
        json_matches = re.findall(r'\{[\s\S]*\}', content)
        for json_str in json_matches:
            try:
                # Sanitize newlines inside string values
                sanitized = sanitize_json_newlines(json_str)
                parsed = json.loads(sanitized)
                return parsed
            except Exception as e:
                print("JSON parsing error:", e)
                print("Attempted JSON string:", json_str)
        print("No valid JSON object found in prompt generator response. Raw response:")
        print(content)
        # Fallback to basic prompt
        return {
            "question_type": "general",
            "domain": "general knowledge",
            "instructional_prompt": f"Carefully analyze the question and select the most accurate answer from the given options."
        }
        
    except Exception as e:
        print(f"Prompt Generator Error: {e}")
        return None

def get_ai_answer(question, options, enhanced_prompt):
    """Get answer from Groq AI using the enhanced prompt"""
    
    if enhanced_prompt:
        prompt = f"""{enhanced_prompt['instructional_prompt']}

Question Type: {enhanced_prompt['question_type']}
Domain: {enhanced_prompt['domain']}

Question: {question}
Options:
""" + "\n".join(f"- {opt}" for opt in options) + """
Debate, test, and deduct between the remaining options. Based on the above analysis, provide ONLY the correct answer from the given options (no explanation, just the answer text)."""
    else:
        # Fallback to basic prompt
        prompt = f"""You are a multiple choice question solver. Given the question and options, reply ONLY with the option text that is the correct answer (no explanation, just the answer).

Question: {question}
Options:
""" + "\n".join(f"- {opt}" for opt in options)
    
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    
    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        print("Answering AI Response:", result)
        
        answer = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        
        # Try to match answer with options
        for option in options:
            if option.lower() in answer.lower():
                return option
        
        return answer.split('\n')[0] if answer else None
        
    except Exception as e:
        print(f"Answering AI Error: {e}")
        return None
