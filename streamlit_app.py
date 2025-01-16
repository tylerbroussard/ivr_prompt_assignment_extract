import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import base64
import requests
from github import Github
from io import StringIO

def load_campaign_data(github_token, repo_name):
    """Load campaign association data from GitHub."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    
    try:
        # Get campaign association CSV content
        csv_content = repo.get_contents("ivrcampaignassociation.csv")
        csv_data = pd.read_csv(StringIO(csv_content.decoded_content.decode()))
        return csv_data
    except Exception as e:
        st.error(f"Error loading campaign data: {str(e)}")
        return None

def get_ivr_content(github_token, repo_name, ivr_name):
    """Fetch IVR XML content from GitHub."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    
    try:
        # Look for the IVR file in the IVRs folder
        ivr_path = f"IVRs/{ivr_name}"
        ivr_content = repo.get_contents(ivr_path)
        return ivr_content.decoded_content.decode()
    except Exception as e:
        st.error(f"Error loading IVR file: {str(e)}")
        return None

def get_available_prompts(github_token, repo_name):
    """Get list of all available .wav files in the repo."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    
    try:
        contents = repo.get_contents("")  # Root directory
        wav_files = [content.name for content in contents if content.name.endswith('.wav')]
        return wav_files
    except Exception as e:
        st.error(f"Error loading prompt files: {str(e)}")
        return []

def get_prompt_audio(github_token, repo_name, prompt_name):
    """Fetch prompt audio file from GitHub."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    
    try:
        audio_content = repo.get_contents(prompt_name)
        return audio_content.decoded_content
    except Exception as e:
        st.warning(f"Audio file not found: {prompt_name}")
        return None

def extract_prompts(xml_content):
    """Extract prompts from XML content."""
    root = ET.fromstring(xml_content)
    prompts_list = []
    
    # First, find all announcement prompts and their enabled status
    announcement_prompts = {}
    for announcement in root.findall('.//announcements'):
        enabled = announcement.find('enabled')
        prompt = announcement.find('prompt')
        if prompt is not None and enabled is not None:
            prompt_id = prompt.find('id')
            if prompt_id is not None:
                announcement_prompts[prompt_id.text] = {
                    'enabled': enabled.text.lower() == 'true'
                }
    
    # Iterate through each module
    for module in root.findall('.//modules/*'):
        module_name = module.find('moduleName')
        
        if module_name is not None:
            module_name = module_name.text
            
            # Find prompts in different possible locations
            prompt_locations = [
                './/filePrompt/promptData/prompt',
                './/announcements/prompt',
                './/prompt/filePrompt/promptData/prompt',
                './/compoundPrompt/filePrompt/promptData/prompt',
                './/promptData/prompt'
            ]
            
            for location in prompt_locations:
                for prompt_elem in module.findall(location):
                    prompt_id = prompt_elem.find('id')
                    prompt_name = prompt_elem.find('name')
                    if prompt_id is not None and prompt_name is not None:
                        prompts_list.append({
                            'ID': prompt_id.text,
                            'Name': prompt_name.text,
                            'Module': module_name,
                            'AudioFile': f"{prompt_name.text}.wav"  # Assuming the wav file matches the prompt name
                        })
    
    # Remove duplicates based on ID while keeping the first occurrence
    unique_prompts = []
    seen_ids = set()
    for prompt in prompts_list:
        if prompt['ID'] not in seen_ids:
            unique_prompts.append(prompt)
            seen_ids.add(prompt['ID'])
            
    return unique_prompts

def main():
    st.set_page_config(page_title="IVR Prompt Explorer", layout="wide")
    
    st.title("IVR Prompt Explorer")
    
    # GitHub configuration
    github_token = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo"]
    
    # Load campaign data
    campaign_data = load_campaign_data(github_token, repo_name)
    
    if campaign_data is not None:
        # Get all available .wav files
        available_prompts = get_available_prompts(github_token, repo_name)
        
        # Create campaign dropdown
        campaigns = campaign_data['Campaign(s)'].unique()
        selected_campaign = st.selectbox(
            "Select Campaign",
            options=campaigns,
            help="Choose a campaign to view associated IVR prompts"
        )
        
        if selected_campaign:
            # Get associated IVR(s)
            associated_ivrs = campaign_data[
                campaign_data['Campaign(s)'] == selected_campaign
            ]['IVR Associated with Campaign(s)'].tolist()
            
            for ivr_name in associated_ivrs:
                st.subheader(f"Prompts for {ivr_name}")
                
                # Get IVR content
                ivr_content = get_ivr_content(github_token, repo_name, ivr_name)
                
                if ivr_content:
                    # Extract prompts
                    prompts = extract_prompts(ivr_content)
                    
                    if prompts:
                        # Create DataFrame
                        df = pd.DataFrame(prompts)
                        
                        # Display prompts with audio player
                        for index, row in df.iterrows():
                            # Check if the audio file exists in the repository
                            if row['AudioFile'] in available_prompts:
                                with st.expander(f"{row['Name']}"):
                                    col1, col2 = st.columns([3, 1])
                                    
                                    with col1:
                                        st.write(f"Module: {row['Module']}")
                                        st.write(f"Audio File: {row['AudioFile']}")
                                    
                                    with col2:
                                        # Get and display audio
                                        audio_data = get_prompt_audio(github_token, repo_name, row['AudioFile'])
                                        if audio_data:
                                            st.audio(audio_data, format='audio/wav')
                                        else:
                                            st.write("Audio not available")
                            
                        # Show prompt count
                        st.info(f"Found {len(prompts)} unique prompts in {ivr_name}")
                    else:
                        st.warning(f"No prompts found in {ivr_name}")
                else:
                    st.error(f"Could not load IVR file: {ivr_name}")

if __name__ == "__main__":
    main()
