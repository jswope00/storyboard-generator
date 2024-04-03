import openai
import os
from dotenv import find_dotenv, load_dotenv
import time
import logging
import re
from datetime import datetime
import requests
import json
import streamlit as st
from streamlit_lottie import st_lottie_spinner, st_lottie


load_dotenv()



#APP CONFIGURATION
APP_TITLE = 'Storyboard Generator'
APP_SUBTITLE = 'This wizard transforms inputs into storyboard suggestions with scenes, scripts, and multimedia suggestions. Scripts adhere to best online pedagogy practices.'
APP_HOW_IT_WORKS = """
                TBD
             """


#AI CONFIGURATION
AI_CLIENT = openai.OpenAI()
AI_MODEL = "gpt-4-turbo-preview"
AI_ASSISTANT_NAME = "Video Scripter"
AI_ASSISTANT_ID = "asst_Pby7mpoi5XlyeOU0jgK9PvLn"
AI_ASSISTANT_INSTRUCTIONS = """You take inputs of various kinds and transform them into effective scripts for educational videos. 

            #Principles
            - Your scripts remain focused and targeted on learning goals. 
            - You may suggest visual or audio elements that will support educational goals using the cognitive principle. 
            - When you suggest visual or audio elements, you consider how to make these elements complementary rather than redundant
            - You use signaling to highlight important ideas or concepts.
            - Your scripts should strive to be clear, concise and unambiguous, avoiding jargon or technical language unless it is necessary to meet the learning outcomes.

            # Response Formatting
            - You format your output by scene. For example:
            **Scene 1: Introduction**
            Lorem Ipsum...
            **Scene 2: Exposition**
            Lorem Ipsum....
            - When you suggest visual or audio elements, you use brackets
            e.g. [visual suggestion: image of a bear]
            - When you use signaling, you bold the word in your output that you want to signal. 

            # Interactions
            - If the user's inputs are unclear, you should ask for clarification to ensure accurate responses.

            """


phases = [
    {
        "id": "name",
        "question": """What is your name?""",
        "sample_answer": "",
        "instructions": """The user will give you their name. Then, welcome the user to the exercise, and explain that you'll help them and provide feedback as they go. End your statement with "I will now give you your first question about the article." """,
        "rubric": """
            1. Name
                    1 point - The user has provided a response in this thread. 
                    0 points - The user has not provided a response. 
        """,
        "label": "GO!",
        "minimum_score": 0
    },
    {
        "id": "about",
        "question": """What is the article about?""",
        "sample_answer":"This article investigates the impact of various video production decisions on student engagement in online educational videos, utilizing data from 6.9 million video watching sessions on the edX platform. It identifies factors such as video length, presentation style, and speaking speed that influence engagement, and offers recommendations for creating more effective educational content.",
        "instructions": "Provide helpful feedback for the following question. If the student has not answered the question accurately, then do not provide the correct answer for the student. Instead, use evidence from the article coach them towards the correct answer. If the student has answered the question correctly, then explain why they were correct and use evidence from the article. Question:",
        "rubric": """
                1. Length
                    1 point - Response is greater than or equal to 150 characters.
                    0 points - Response is less than 150 characters. 
                2. Key Points
                    2 points - The response mentions both videos AND student engagement rates
                    1 point - The response mentions either videos OR student engagement rates, but not both
                    0 points - The response does not summarize any important points in the article. 
        """,
        "minimum_score": 2
    },
    {
       "id": "methdologies",
       "question": "Summarize the methodology(s) used.",
       "sample_answer": "The study gathered data around video watch duration and problem attempts from the edX logs. These metrics served as a proxy for engagement. Then it compared that with video attributes like length, speaking rate, type, and production style, to determine how video production affects engagement.",
       "instructions": "Provide helpful feedback for the following question. If the student has not answered the question accurately, then do not provide the correct answer for the student. Instead, use evidence from the article coach them towards the correct answer. If the student has answered the question correctly, then explain why they were correct and use evidence from the article. Question:",
       "rubric": """
               1. Correctness
                   1 point - Response is correct and based on facts in the paper
                   0 points - Response is incorrect or not based on facts in the paper
               """,
       "minimum_score": 1
    },
    {
        "id": "findings",
        "question": "What were the main findings in the article?",
        "sample_answer": "Shorter videos are more engaging; Faster-speaking instructors hold students' attention better; High production value does not necessarily correlate with higher engagement;",
        "instructions": "Provide helpful feedback for the following question. If the student has not answered the question accurately, then do not provide the correct answer for the student. Instead, use evidence from the article coach them towards the correct answer. If the student has answered the question correctly, then explain why they were correct and use evidence from the article. Question:",
        "rubric": """
            1. Correctness
                    2 points - Response includes two or more findings or recommendations from the study
                    1 point - Response includes only one finding or recommendation form the study
                    0 points - Response includes no findings or recommendations or is not based on facts in the paper
                    """,
        "minimum_score": 1
    },
    {
        "id": "limitations",
        "question": "What are some of the weaknesses of this study?",
        "sample_answer": "The study cannot measure true student engagement, and so it must use proxies; The study could not track any offline video viewing; The study only used data from math/science courses;",
        "instructions": "Provide helpful feedback for the following question. If the student has not answered the question accurately, then do not provide the correct answer for the student. Instead, use evidence from the article coach them towards the correct answer. If the student has answered the question correctly, then explain why they were correct and use evidence from the article. Question:",
        "rubric": """
            1. Correctness
                    2 points - Response includes two or more limitations of the study
                    1 point - Response includes only one limitation in the study
                    0 points - Response includes no limitations or is not based on facts in the paper
                2. Total Score
                    The total sum of their scores. 
            """,
        "minimum_score": 1
    }
    #Add more steps as needed
    
]

current_question_index = st.session_state.current_question_index if 'current_question_index' in st.session_state else 0


class AssistantManager:
    thread_id = ""
    assistant_id = AI_ASSISTANT_ID


    if 'current_question_index' not in st.session_state:
        st.session_state.thread_obj = []


    def __init__(self, model: str = AI_MODEL):
        self.client = AI_CLIENT
        self.model = AI_MODEL
        self.assistant = None
        self.thread = None
        self.run = None
        self.summary = None

        # Retrieve existing assistant and thread if IDs are already set
        if AssistantManager.assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(
                assistant_id=AssistantManager.assistant_id
            )
        if AssistantManager.thread_id:
            self.thread = self.client.beta.threads.retrieve(
                thread_id=AssistantManager.thread_id
            )

    def create_assistant(self, name, instructions, tools):
        if not self.assistant:
            assistant_obj = self.client.beta.assistants.create(
                name=name, instructions=instructions, tools=tools, model=self.model
            )
            AssistantManager.assistant_id = assistant_obj.id
            self.assistant = assistant_obj
            print(f"AssisID:::: {self.assistant.id}")

    def create_thread(self):
        if not self.thread:
            if st.session_state.thread_obj:
                print(f"Grabbing existing thread...")
                thread_obj = st.session_state.thread_obj
            else:
                print(f"Creating and saving new thread")
                thread_obj = self.client.beta.threads.create()
                st.session_state.thread_obj = thread_obj

            AssistantManager.thread_id = thread_obj.id
            self.thread = thread_obj
            print(f"ThreadID::: {self.thread.id}")

    def add_message_to_thread(self, role, content):
        if self.thread:
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id, role=role, content=content
            )

    def run_assistant(self, instructions):
        if self.thread and self.assistant:
            self.run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id,
                instructions=instructions,
            )

    def process_message(self):
        if self.thread:
            messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
            summary = []

            last_message = messages.data[0]
            role = last_message.role

            #st.text(last_message)
            #if last_message.content[0].text.value.feedback:
            #    response = last_message.content[0].text.value.feedback
            #else:
            response = last_message.content[0].text.value
            summary.append(response)

            self.summary = "\n".join(summary)
            

            # for msg in messages:
            #     role = msg.role
            #     content = msg.content[0].text.value
            #     print(f"SUMMARY-----> {role.capitalize()}: ==> {content}")

    def call_required_functions(self, required_actions):
        if not self.run:
            return
        tool_outputs = []

        for action in required_actions["tool_calls"]:
            func_name = action["function"]["name"]
            arguments = json.loads(action["function"]["arguments"])

            if func_name == "respond":
                output = respond(structured_response=arguments["structured_response"])
            
                final_str = ""
                for item in output:
                    final_str += "".join(item)

                tool_outputs.append({"tool_call_id": action["id"], "output": final_str})
            else:
                raise ValueError(f"Unknown function: {func_name}")

        print("Submitting outputs back to the Assistant...")
        self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread.id, run_id=self.run.id, tool_outputs=tool_outputs
        )

    # for streamlit
    def get_summary(self):
        return self.summary

    def wait_for_completion(self):
        if self.thread and self.run:
            while True:
                time.sleep(5)
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread.id, run_id=self.run.id
                )
                print(f"RUN STATUS:: {run_status.model_dump_json(indent=4)}")


                if run_status.status == "completed":
                    self.process_message()
                    prompt_tokens = run_status.usage.prompt_tokens
                    completion_tokens = run_status.usage.completion_tokens
                    cost = prompt_tokens * (10/1000000) + completion_tokens * (30/1000000)
                    st.markdown("**cost:** " + str(cost))
                    break
                elif run_status.status == "requires_action":
                    print("FUNCTION CALLING NOW...")
                    self.call_required_functions(
                        required_actions=run_status.required_action.submit_tool_outputs.model_dump()
                    )

    def run_steps(self):
        run_steps = self.client.beta.threads.runs.retrieve(
            thread_id=self.thread.id, run_id=self.run.id
        )
        st.text(f"Run-Steps::: {run_steps}")


def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

def spinner():   # Animated json spinner

    @st.cache_data
    def load_lottie_url(url:str):
        r= requests.get(url)
        if r.status_code != 200:
            return
        return r.json()


    lottie_url = "https://lottie.host/0d83def0-10e6-4c0b-8da6-651282597a75/OQW2u80OtM.json"
    lottie_json = load_lottie_url(lottie_url)

    st_lottie(lottie_json, height=200)
    time.sleep(5)  # Simulate some processing time


class LottieSpinner:
    def __enter__(self):
        # Setup code goes here, for example, starting a spinner animation
        spinner()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Teardown code goes here, for example, stopping the spinner animation
        # Returning False propagates exceptions, True suppresses them
        return False

def lottie_spinner():
    return LottieSpinner()


def handle_assistant_grading(index, manager):

    instructions = build_instructions(index, True)
    manager.run_assistant(instructions)
    manager.wait_for_completion()

    #get the score summary
    summary = "SCORE: " + manager.get_summary()
    #save the score summary
    st.session_state[f"phase_{index}_rubric"] = summary

    print(f"RUBRIC SCORE: {summary}")

    #write the score summary
    #st.write(summary)

    
    #save the numeric score
    st.session_state[f"phase_{index}_score"] = score
    #st.write("COMPUTER SAVED SCORE: " + str(st.session_state[f"phase_{index}_score"]))
    


st.markdown(
    """<style>
div[class*="stTextInput"] > label > div[data-testid="stMarkdownContainer"] > p, 
div[class*="stTextArea"] > label > div[data-testid="stMarkdownContainer"] > p{
    font-size: 32px;
    font-weight: bold;
}
    </style>
    """, unsafe_allow_html=True)


def main():
    # Initialize session state variables if they don't exist
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0
    if 'current_question_index' not in st.session_state:
        st.session_state.thread_obj = []

    st.title(APP_TITLE)
    st.write(APP_SUBTITLE)

    if APP_HOW_IT_WORKS:
        with st.expander("Learn how this works", expanded=False):
            st.markdown(APP_HOW_IT_WORKS)

    #Create the assistant one time. Only if the Assistant ID is not found, create a new one. 
    manager = AssistantManager()

    manager.create_assistant(
        name=AI_ASSISTANT_NAME,
        instructions=AI_ASSISTANT_INSTRUCTIONS,
        tools=""
    )
    #Create a new thread, or grab the existing thread if it exists. 
    manager.create_thread()


    # User input sections
    topic_content = st.text_area("Enter the content or topic to be turned into a storyboard:", max_chars=50000, key="topic_content", value = "")
    learning_objective = st.text_area("Specify learning objective(s) (optional):", max_chars=1000, key="learning_objective")

    audience_level = st.selectbox("Audience:", ['Grade School', 'High School', 'University', 'Other'], index=2, key="audience_level")
    custom_audience_level = st.text_input("Specify other level:", key="custom_audience_level") if audience_level == 'Other' else None

    prior_knowledge = st.selectbox("Prior Knowledge:", ['Basic', 'Intermediate', 'Experts', 'Other'], index=0, key="prior_knowledge")
    custom_prior_knowledge = st.text_input("Specify other level:", key="custom_prior_knowledge") if prior_knowledge == 'Other' else None

    # Question configuration inputs
    video_duration = st.slider("How many minutes would you like the video?",min_value=3, max_value=10,value=5,)
    st.write("Which Storyboard Elements would you like to generate?")
    col1, col2, col3 = st.columns(3)
    with col1:
        video_settings_checkboxes = {
            "Script": st.checkbox("Script",key="video_script",value="true")
            }
    with col2:
        video_settings_checkboxes.update({
            "Multimedia Suggestions": st.checkbox("Multimedia Suggestions",key="video_media",value="true")
        })
    with col3:
        video_settings_checkboxes.update({
        "Audio Suggestions": st.checkbox("Audio Suggestions",key="video_audio",value="true")
        })

    st.write("Tone and Story Devices")
    
    # Initialize the dictionary
    tone_checkboxes = {}
    
    col1, col2, col3 = st.columns(3)
    with col1:
        tone_checkboxes["Warm and Friendly"] = st.checkbox("Warm and Friendly", key="warm_friendly_tone", value=False)
    with col2:
        tone_checkboxes["Professional"] = st.checkbox("Professional", key="professional_tone", value=True)
    with col3:
        tone_checkboxes["Use Real-world Examples"] = st.checkbox("Use Real-World Examples", key="use_examples_tone", value=True)

    # Filter the dictionary to keep only the checked items
    checked_tones = [tone for tone, checked in tone_checkboxes.items() if checked]



    uploaded_file = st.file_uploader("Or, upload your own tone source docs", help="If you upload a document here, the app will attempt to mimic the style and tone of the uploaded document.")

    
    output_type = st.selectbox("Output Type:", ["Text", "CSV"], key="output_type")

    with st.expander("Advanced Settings", expanded=False):
        adv_multimedia_principle = st.checkbox("Adhere to the Multimedia Principle",key="adv_multimedia_principle",value="true", help="Adhere to the Multimedia principle which states that learners learn better when it is presented through both words and visuals than by words alone.")
        adv_contiguity_principle = st.checkbox("Adhere to the Contiguity Principle",key="adv_contiguity_principle",value="true", help="Adhere to the contiguity principle which emphasizes the importance of placing text near corresponding visuals.")
        adv_coherence_principle = st.checkbox("Adhere to the Coherence Principle",key="adv_coherence_principle",value="true", help="Adhere to the coherence principle by not including distracting or purely decorational media.")
        adv_signaling = st.checkbox("Use signaling",key="adv_signaling",value="true", help="Use signaling where appropriate to stress the key learning concepts. Indicate signaling with bolded words.")
    
# COMPILE THE INSTRUCTIONS
    if custom_audience_level:
        audience_level = custom_audience_level
    if custom_prior_knowledge:
        prior_knowledge = custom_prior_knowledge

    
    video_settings_prompt = ""
    if video_settings_checkboxes:
        video_settings_prompt = "and includes " + ", ".join(video_settings_checkboxes)

    instructions = (
        f"Please write a storyboard for a video that is {video_duration} minutes long {video_settings_prompt}"
        f" for an audience that is {audience_level} level "
        f"with {prior_knowledge} knowledge of the topic. I will provide the topic at the bottom of this message. \n"
    )

    if checked_tones:
        instructions += f"The tone should be {', '.join(checked_tones)}. \n"

    if learning_objective:
        instructions += (
            f"Please focus on the following learning objective(s): {learning_objective}"
            )

    instructions += " Adhere to the Multimedia principle which states that learners learn better when it is presented through both words and visuals than by words alone.\n " if adv_multimedia_principle else ""
    instructions += " Adhere to the contiguity principle which emphasizes the importance of placing text near corresponding visuals.\n " if adv_contiguity_principle else ""
    instructions += " Adhere to the coherence principle by not including distracting or purely decorational media.\n " if adv_coherence_principle else ""
    instructions += " Use signaling where appropriate to stress the key learning concepts. Indicate signaling with bolded words.\n " if adv_signaling else ""

    if output_type == "CSV":
        instructions += (
            f"Please provide your output as a CSV with appropriate headers, where every row is a scene.\n"
            )

    if len(topic_content) < 150:
        instructions += (
            f"The topic is \n"
            f"===========\n"
            f"{topic_content}"
            )
    else:
        instructions += (
            f"Please rely on the following text, but convert it into a storyboard based on the parameters provided \n"
            f"===========\n"
            f"{topic_content}"
            )

    


    with st.expander("View/edit full prompt"):
        final_instructions = st.text_area(
                label="Prompt",
                height=100,
                max_chars=60000,
                value=instructions,
                key="init_prompt",
            )


    submit_button = st.button(label="Submit", type="primary", key="submit ")         
    if submit_button:
        # provide the instructions to the AI
        manager.run_assistant(final_instructions)
        # Wait for completions and process messages
        manager.wait_for_completion()

        #get the AI Feedback
        summary = manager.get_summary()
        #save the AI Feedback
        st.session_state[f"ai_summary"] = summary
        #write the AI feedback
        st.write(summary)




        


if __name__ == "__main__":
    main()

