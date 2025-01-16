import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import re
from io import StringIO
import base64
import os

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
                        prompts_list.append({
                            'ID': prompt_id.text,
                            'Name': prompt_name.text,
                            'Module': module_name,
                            'Type': 'Announcement' if prompt_id.text in announcement_prompts else 'Play',
                            'Enabled': enabled
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

def main():
    st.set_page_config(page_title="IVR Prompt Extractor", layout="wide")
    
    st.title("IVR Prompt Extractor")
    st.markdown("""
    Select a campaign to view its associated IVR prompts.
    """)

    # Read IVR-campaign associations
    campaign_df = pd.read_csv('ivrcampaignassociation.csv')
    
    # Get list of available IVR files
    available_ivrs = [f.replace('.five9ivr', '') for f in os.listdir('IVRs') if f.endswith('.five9ivr')]
    
    # Create a mapping of campaigns to IVRs, only including available IVRs
    campaign_to_ivr = {}
    unavailable_campaigns = []
    for _, row in campaign_df.iterrows():
        ivr = row['IVR Associated with Campaign(s)']
        campaigns = str(row['Campaign(s)']).split(',')
        for campaign in campaigns:
            campaign = campaign.strip()
            if campaign:  # Skip empty strings
                if ivr in available_ivrs:
                    campaign_to_ivr[campaign] = ivr
                else:
                    unavailable_campaigns.append((campaign, ivr))

    # Get unique campaigns for dropdown
    campaigns = sorted(list(campaign_to_ivr.keys()))
    
    # Display warning about unavailable IVRs if any
    if unavailable_campaigns:
        st.warning("Some campaigns are mapped to IVR files that are not available in the IVRs directory:")
        for campaign, ivr in unavailable_campaigns:
            st.write(f"- Campaign '{campaign}' -> IVR '{ivr}'")
        st.write("These campaigns will not be shown in the dropdown.")
    
    # Campaign selector
    selected_campaign = st.selectbox(
        "Select a Campaign",
        options=campaigns,
        index=None,
        placeholder="Choose a campaign..."
    )

    if selected_campaign:
        # Get associated IVR file
        ivr_name = campaign_to_ivr[selected_campaign]
        ivr_path = os.path.join('IVRs', f"{ivr_name}.five9ivr")
        
        try:
            # Read and process the IVR file
            with open(ivr_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            prompts = extract_prompts(xml_content)
            
            if prompts:
                # Convert to DataFrame
                df = pd.DataFrame(prompts)
                
                # Display prompts
                st.write(f"### Prompts in {ivr_name}")
                st.write(f"Found {len(prompts)} prompts:")
                
                # Format the Status column
                df['Status'] = df['Enabled'].map({True: '✅ In Use', False: '❌ Not In Use'})
                
                # Display the DataFrame with formatted columns
                display_df = df[['Name', 'Module', 'Type', 'Status']].copy()
                st.dataframe(display_df, use_container_width=True)
                
                # Provide download link
                st.markdown(get_download_link(df, f"{ivr_name}_prompts.csv", "Download Prompts as CSV"), unsafe_allow_html=True)
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
