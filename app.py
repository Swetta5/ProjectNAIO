import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time
import requests  # Required for the Webhook trigger

# --- CONFIGURATION ---
SHEET_NAME = "Amazon_Data"
WORKSHEET_NAME = "demo"

# --- AUTHENTICATION ---
@st.cache_resource
def get_sheet():
    # Define the scope
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Load Credentials from Streamlit Secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    return sheet

# --- LOGIN ---
def login():
    st.title("🔐 Project 9: VoC Analytics")
    c1, c2 = st.columns([1,2])
    with c1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username == "admin" and password == "admin":
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("Try admin/admin")

# --- MAIN APP ---
def main():
    st.set_page_config(layout="wide", page_title="VoC Dashboard")
    
    # Check Login Status
    if "logged_in" not in st.session_state:
        login()
        return

    # --- SIDEBAR: INPUT ---
    with st.sidebar:
        st.header("📝 New Review Simulation")
        st.caption("Simulate a user posting a review on the App Store")
        
        # 1. Title & Body
        review_title = st.text_input("Review Title", "Great app but slow")
        review_body = st.text_area("Review Body", "I love the features but it loads very slowly on my Android.", height=150)
        
        # 2. Star Rating
        stars = st.slider("Star Rating", 1, 5, 4)
        
        # 3. Category Selection (With "Other" Logic)
        cat_options = [
            "home", "wireless", "industrial_supplies", "luggage", "office_product", 
            "pet_products", "kitchen", "apparel", "furniture", "video_games", 
            "home_improvement", "lawn_and_garden", "book", "drugstore", 
            "automotive", "sports", "digital_ebook_purchase", "shoes", "grocery", 
            "beauty", "pc", "electronics", "toy", "baby_product", 
            "personal_care_appliances", "jewelry", "watch", "camera", 
            "digital_video_download", "musical_instruments", "Other"
        ]
        selected_cat = st.selectbox("Product Category", cat_options)
        
        if selected_cat == "Other":
            product_cat = st.text_input("Enter Custom Category", "crypto_wallet")
        else:
            product_cat = selected_cat

        # 4. Language Selection (With "Other" Logic)
        lang_options = ["en", "de", "es", "fr", "ja", "zh", "Other"]
        selected_lang = st.selectbox("Language Code", lang_options)
        
        if selected_lang == "Other":
            lang = st.text_input("Enter Language Code (e.g., 'it', 'ru')", "it")
        else:
            lang = selected_lang
        
        st.divider()

        if st.button("🚀 Post Review"):
            try:
                sheet = get_sheet()
                
                # --- INTELLIGENT ID GENERATION ---
                # 1. Calculate Index Number
                existing_data = sheet.get_all_values()
                next_index = len(existing_data)
                
                # 2. Generate Format-Matching IDs
                random_num = f"{random.randint(1000000, 9999999)}"
                clean_lang = lang.lower().strip()
                
                new_review_id = f"{clean_lang}_{random_num}"
                new_product_id = f"product_{clean_lang}_{random_num}"
                new_reviewer_id = f"reviewer_{clean_lang}_{random_num}"
                
                # 3. Create Row (Aligned to Schema)
                new_row = [
                    next_index,      # Column A: Sequential Index
                    new_review_id,   # Column B: ID
                    new_product_id,  # Column C: Product ID
                    new_reviewer_id, # Column D: Reviewer ID
                    stars,           # Column E: Stars
                    review_body,     # Column F: Body
                    review_title,    # Column G: Title
                    lang,            # Column H: Language
                    product_cat,     # Column I: Category
                    "", "", "", ""   # Columns J-M: Empty slots for AI
                ]
                
                sheet.append_row(new_row)
                st.success(f"Posted! Index: {next_index} | ID: {new_review_id}")
                
                # --- TRIGGER N8N (WEBHOOK BYPASS) ---
                webhook_url = "https://swetta.app.n8n.cloud/webhook-test/review"
                
                payload = {
                    "review_body": review_body,
                    "review_id": new_review_id,
                    "row_number": next_index + 1  # 1-based index
                }
                
                try:
                    requests.post(webhook_url, json=payload)
                    st.info("⚡ AI Pipeline Triggered Instantly!")
                except Exception as e:
                    st.warning(f"Webhook failed to trigger: {e}")
                # ------------------------------------
                
            except Exception as e:
                st.error(f"Error: {e}")

    # --- MAIN DASHBOARD AREA ---
    st.title("📊 Live Customer Insights")
    st.markdown("Real-time analysis powered by **n8n** and **GPT-4o**")
    
    # Refresh Button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

    # Load Data
    try:
        sheet = get_sheet()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # METRICS SECTION
        if not df.empty:
            c1, c2, c3 = st.columns(3)
            
            # Total Count
            c1.metric("Total Reviews", len(df))
            
            # Negative Sentiment Count
            if 'sentiment_label' in df.columns:
                neg = len(df[df['sentiment_label'] == "Negative"])
                c2.metric("Negative Alerts", neg, delta_color="inverse")
            else:
                c2.metric("Negative Alerts", 0)

            # Average Rating
            if 'stars' in df.columns:
                try:
                    # Force convert to numeric just in case
                    avg = pd.to_numeric(df['stars'], errors='coerce').mean()
                    c3.metric("Avg Rating", f"{avg:.1f} ⭐")
                except:
                    c3.metric("Avg Rating", "N/A")

            st.divider()

            # REVIEW FEED (Last 5 Items)
            st.subheader("Latest Processed Reviews")
            
            # Iterate backwards through the last 5 rows
            # We use tail(5) and [::-1] to show newest first
            for i, row in df.tail(5)[::-1].iterrows():
                with st.container(border=True):
                    cols = st.columns([1, 2])
                    
                    # Left Column: User Input
                    with cols[0]:
                        # Handle potential missing keys gracefully
                        r_id = row.get('review_id', 'N/A')
                        r_lang = row.get('language', 'N/A')
                        r_title = row.get('review_title', 'No Title')
                        r_body = row.get('review_body', 'No Body')
                        r_cat = row.get('product_category', 'General')
                        
                        st.caption(f"ID: {r_id} | Lang: {r_lang}")
                        st.write(f"**{r_title}**")
                        st.write(f"\"{r_body}\"")
                        st.caption(f"Category: {r_cat}")
                    
                    # Right Column: AI Output
                    with cols[1]:
                        sentiment = row.get('sentiment_label')
                        
                        # Only show results if AI has processed the row
                        if sentiment:
                            # Color coding
                            if sentiment == "Positive":
                                color = "green"
                            elif sentiment == "Negative":
                                color = "red"
                            else:
                                color = "gray"
                                
                            st.markdown(f"**Sentiment:** :{color}[{sentiment}]")
                            st.markdown(f"**Topics:** `{row.get('topics')}`")
                            st.text_area("🤖 Draft Reply:", value=row.get('ai_reply'), height=100, disabled=True, key=f"txt_{i}")
                        else:
                            st.warning("⚙️ Processing...")

    except Exception as e:
        st.error(f"Connection Error: {e}")

if __name__ == "__main__":
    main()