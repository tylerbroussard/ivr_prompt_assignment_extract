import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import re
from io import StringIO
import base64

def extract_prompts(xml_content):
    """Extract prompts from XML content."""
    root = ET.fromstring(xml_content)
    prompts = {}
    
    # Iterate through each module
    for module in root.findall('.//modules/*'):
        module_name = module.find('moduleName')
        if module_name is not None:
            module_name = module_name.text
            
            # Look for prompts in filePrompt/promptData/prompt
            for prompt_elem in module.findall('.//filePrompt/promptData/prompt'):
                prompt_id = prompt_elem.find('id')
                prompt_name = prompt_elem.find('name')
                if prompt_id is not None and prompt_name is not None:
                    prompt_key = f"{prompt_id.text}_{module_name}"  # Use composite key to handle same ID in different modules
                    prompts[prompt_key] = {
                        'ID': prompt_id.text,
                        'Name': prompt_name.text,
                        'Module': module_name
                    }
            
            # Also check for prompts in any other locations using the same structure
            for prompt_data in module.findall('.//promptData'):
                prompt = prompt_data.find('prompt')
                if prompt is not None:
                    prompt_id = prompt.find('id')
                    prompt_name = prompt.find('name')
                    if prompt_id is not None and prompt_name is not None:
                        prompt_key = f"{prompt_id.text}_{module_name}"
                        prompts[prompt_key] = {
                            'ID': prompt_id.text,
                            'Name': prompt_name.text,
                            'Module': module_name
                        }
    
    # Convert to list of unique prompts
    unique_prompts = list(prompts.values())
    # Sort by name
    unique_prompts.sort(key=lambda x: x['Name'])
    
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
    This app extracts prompts from IVR XML scripts. Upload one or more XML files to begin.
    """)

    # File uploader
    uploaded_files = st.file_uploader(
        "Upload Five9 IVR or XML files", 
        type=['five9ivr', 'xml'], 
        accept_multiple_files=True,
        help="You can upload multiple XML files at once"
    )

    if uploaded_files:
        all_results = []
        
        # Process each file
        for uploaded_file in uploaded_files:
            st.subheader(f"Results for: {uploaded_file.name}")
            
            try:
                # Read file content
                content = uploaded_file.read().decode('utf-8')
                
                # Extract prompts
                prompts = extract_prompts(content)
                
                if prompts:
                    # Create DataFrame for this file
                    df = pd.DataFrame(prompts)
                    
                    # Add filename column
                    df['Source File'] = uploaded_file.name
                    
                    # Add to all results
                    all_results.append(df)
                    
                    # Display results for this file
                    st.dataframe(
                        df[['Name', 'ID']],
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Show prompt count
                    st.info(f"Found {len(prompts)} unique prompts in {uploaded_file.name}")
                    
                else:
                    st.warning(f"No prompts found in {uploaded_file.name}")
                
                st.divider()
                
            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        
        # If we have results, offer combined analysis
        if all_results:
            st.header("Combined Analysis")
            
            # Combine all results
            combined_df = pd.concat(all_results, ignore_index=True)
            
            # Analysis tabs
            tab1, tab2, tab3 = st.tabs(["Summary", "Duplicate Analysis", "Export"])
            
            with tab1:
                st.subheader("Summary Statistics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Files", len(uploaded_files))
                with col2:
                    st.metric("Total Prompts", len(combined_df))
                with col3:
                    st.metric("Unique Prompt IDs", combined_df['ID'].nunique())
            
            with tab2:
                st.subheader("Duplicate Prompt Analysis")
                
                # Find duplicates based on ID
                duplicates = combined_df[combined_df.duplicated(subset=['ID'], keep=False)]
                if not duplicates.empty:
                    st.dataframe(
                        duplicates.sort_values('ID'),
                        hide_index=True,
                        use_container_width=True
                    )
                    st.warning(f"Found {len(duplicates)//2} duplicate prompt IDs across files")
                else:
                    st.success("No duplicate prompt IDs found across files")
            
            with tab3:
                st.subheader("Export Options")
                
                # Export individual file results
                for df in all_results:
                    filename = f"prompts_{df['Source File'].iloc[0]}.csv"
                    st.markdown(
                        get_download_link(df, filename, f"Download results for {df['Source File'].iloc[0]}"),
                        unsafe_allow_html=True
                    )
                
                # Export combined results
                st.markdown(
                    get_download_link(combined_df, "all_prompts.csv", "Download combined results"),
                    unsafe_allow_html=True
                )

if __name__ == "__main__":
    main()
