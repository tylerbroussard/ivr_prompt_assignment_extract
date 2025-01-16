import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import re
from io import StringIO
import base64
import os
from pathlib import Path

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
        
        # Check if module is disconnected
        is_disconnected = False
        module_id = None
        if module.find('moduleId') is not None:
            module_id = module.find('moduleId').text
            # If all connection IDs are the same as the module ID, it's disconnected
            all_connections = []
            for tag in ['ascendants', 'exceptionalDescendant', 'singleDescendant']:
                connections = module.findall(f'./{tag}')
                all_connections.extend([conn.text for conn in connections])
            
            if all_connections and all(conn == module_id for conn in all_connections):
                is_disconnected = True
        
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
                        # Check if this prompt has announcement settings
                        enabled = announcement_prompts.get(prompt_id.text, {}).get('enabled', None)
                        # If not an announcement prompt, mark as In Use/Not In Use
                        if enabled is None:
                            enabled = not is_disconnected
                        
                        # Get the wav filename from the prompt name
                        wav_filename = f"{prompt_name.text}.wav"
                        
                        prompts_list.append({
                            'ID': prompt_id.text,
                            'Name': prompt_name.text,
                            'Module': module_name,
                            'Type': 'Announcement' if prompt_id.text in announcement_prompts else 'Play',
                            'Enabled': enabled,
                            'WavFile': wav_filename
                        })
    
    # Sort by name and remove duplicates based on ID
    unique_prompts = []
    seen_ids = set()
    for prompt in sorted(prompts_list, key=lambda x: x['Name']):
        if prompt['ID'] not in seen_ids:
            unique_prompts.append(prompt)
            seen_ids.add(prompt['ID'])
            
    return unique_prompts

def get_download_link(df, filename, text):
    """Generate a download link for the dataframe."""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 {text}</a>'
    return href

def get_audio_html(wav_path):
    """Generate HTML for audio player if WAV file exists."""
    if os.path.exists(wav_path):
        return f'<audio controls><source src="data:audio/wav;base64,{base64.b64encode(open(wav_path, "rb").read()).decode()}" type="audio/wav">Your browser does not support the audio element.</audio>'
    return "❌ Audio file not found"

def main():
    st.set_page_config(page_title="IVR Prompt Extractor", layout="wide")
    
    st.title("IVR Prompt Extractor")
    st.markdown("""
    Select a campaign to view and play its associated IVR prompts.
    """)

    # Read campaign-IVR associations
    campaign_df = pd.read_csv('campaignivrs.csv')
    
    # Get list of available IVR files
    available_ivrs = set(os.listdir('IVRs'))
    
    # Filter campaigns to only those with available IVR files
    available_campaigns = []
    for _, row in campaign_df.iterrows():
        if row['IVR'] in available_ivrs:
            available_campaigns.append(row['Campaign'])
    
    if not available_campaigns:
        st.error("No campaigns found with available IVR files.")
        return
    
    # Campaign selector
    selected_campaign = st.selectbox(
        "Select a Campaign",
        options=sorted(available_campaigns),
        index=None,
        placeholder="Choose a campaign..."
    )

    if selected_campaign:
        # Get associated IVR file
        ivr_file = campaign_df[campaign_df['Campaign'] == selected_campaign]['IVR'].iloc[0]
        ivr_path = os.path.join('IVRs', ivr_file)
        
        try:
            # Read and process the IVR file
            with open(ivr_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            prompts = extract_prompts(xml_content)
            
            if prompts:
                # Convert to DataFrame
                df = pd.DataFrame(prompts)
                
                # Display prompts
                st.write(f"### Prompts in {ivr_file}")
                st.write(f"Found {len(prompts)} prompts:")
                
                # Create columns for better layout
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Format the Status column
                    df['Status'] = df.apply(
                        lambda x: '✅ Active' if x['Enabled'] and x['Type'] == 'Announcement'
                        else '❌ Disabled' if not x['Enabled'] and x['Type'] == 'Announcement'
                        else '✅ In Use' if x['Enabled'] and x['Type'] == 'Play'
                        else '❌ Not In Use',
                        axis=1
                    )
                    
                    # Display the DataFrame with formatted columns
                    display_df = df[['Name', 'Module', 'Type', 'Status']].copy()
                    st.dataframe(display_df, use_container_width=True)
                
                with col2:
                    # Provide download link
                    st.markdown(get_download_link(df, f"{ivr_file}_prompts.csv", "Download Prompts as CSV"), unsafe_allow_html=True)
                
                # Display audio players for each prompt
                st.write("### Play Prompts")
                for _, prompt in df.iterrows():
                    wav_path = prompt['WavFile']
                    if os.path.exists(wav_path):
                        st.write(f"**{prompt['Name']}** ({prompt['Status']})")
                        st.markdown(get_audio_html(wav_path), unsafe_allow_html=True)
                        st.divider()
                
            else:
                st.warning("No prompts found in the IVR file.")
                
        except FileNotFoundError:
            st.error(f"IVR file not found: {ivr_path}")
        except ET.ParseError:
            st.error("Error parsing the IVR file. The file may be corrupted or in an invalid format.")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
