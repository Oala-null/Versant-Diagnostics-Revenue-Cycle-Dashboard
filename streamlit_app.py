import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime, timedelta
import os
import re
import random
from io import BytesIO
import base64

# Explicitly add openpyxl as a dependency
try:
    import openpyxl
except ImportError:
    st.error("Missing required dependency: openpyxl. Please install it with pip install openpyxl")

# Set page config for Streamlit
st.set_page_config(
    page_title="Versant Diagnostics Revenue Cycle Analysis",
    page_icon="📊",
    layout="wide"
)

# -------------------------------------------------------------
# Data Loading Functions
# -------------------------------------------------------------
def load_data_from_upload(uploaded_file):
    """Load data from uploaded file"""
    try:
        # Get file extension to handle different file formats
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        if file_ext in ['xlsx', 'xls']:
            # For Excel files
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        elif file_ext == 'csv':
            # Allow CSV files as well
            df = pd.read_csv(uploaded_file)
        else:
            st.sidebar.error(f"Unsupported file format: {file_ext}. Please upload Excel or CSV files.")
            return pd.DataFrame()
        
        # Ensure Procedure Code is treated as a string
        if 'Procedure Code' in df.columns:
            df['Procedure Code'] = df['Procedure Code'].astype(str)
            
        st.sidebar.success("File uploaded successfully!")
        return df
    except Exception as e:
        st.sidebar.error(f"Error loading uploaded file: {str(e)}")
        return pd.DataFrame()

def create_sample_data():
    """Create sample data for demonstration"""
    # Create date range
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(100)]
    
    # Create sample data
    data = {
        'Date of Service': dates,
        'Date of Entry': [d + timedelta(days=random.randint(1, 5)) for d in dates],
        'Date of Initial Bill': [d + timedelta(days=random.randint(7, 30)) for d in dates],
        'Charge Line Item Amount': [random.uniform(500, 2000) for _ in range(100)],
        'Total Payments Amount': [random.uniform(300, 1800) for _ in range(100)],
        'Total Adjustments Amount': [random.uniform(0, 500) for _ in range(100)],
        'Total Contractual Adjustment Amount': [random.uniform(0, 300) for _ in range(100)],
        'Total Other Adjustment Amount': [random.uniform(0, 200) for _ in range(100)],
        'Charge Line Item Balance': [random.uniform(0, 500) for _ in range(100)],
        'Accession #': [f'ACC{i:05d}' for i in range(100)],
        'Procedure Code': [str(random.choice(['88305', '88342', '88341', '88360', '88312'])) for _ in range(100)],
        'Primary Payer Name': [random.choice(['Medicare', 'Medicaid', 'Blue Cross', 'UnitedHealth', 'Aetna']) for _ in range(100)],
        'Primary Payer Payment Amount': [random.uniform(300, 1500) for _ in range(100)],
        'Location of Service Name': [random.choice(['Main Hospital', 'North Clinic', 'South Clinic', 'East Wing', 'West Wing']) for _ in range(100)]
    }
    
    df = pd.DataFrame(data)
    
    # Calculate derived fields
    df['Days to Bill'] = (df['Date of Initial Bill'] - df['Date of Service']).dt.days
    df['Collection Rate'] = (df['Total Payments Amount'] / df['Charge Line Item Amount'] * 100)
    df['Service Month'] = df['Date of Service'].dt.to_period('M').astype(str)
    
    return df

def preprocess_data(df):
    """Preprocess and clean the data"""
    if df.empty:
        return df
    
    # Convert date columns to datetime
    date_columns = ['Date of Service', 'Date of Entry', 'Date of Initial Bill']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Ensure Procedure Code is always treated as string to prevent type comparison errors
    if 'Procedure Code' in df.columns:
        df['Procedure Code'] = df['Procedure Code'].astype(str)
    
    # Calculate derived fields for analysis
    if 'Date of Service' in df.columns and 'Date of Initial Bill' in df.columns:
        df['Days to Bill'] = (df['Date of Initial Bill'] - df['Date of Service']).dt.days
    
    # Calculate collection rate if needed
    if 'Charge Line Item Amount' in df.columns and 'Total Payments Amount' in df.columns:
        df['Collection Rate'] = (df['Total Payments Amount'] / df['Charge Line Item Amount'] * 100)
        
    # Add year-month field for time series analysis
    if 'Date of Service' in df.columns:
        df['Service Month'] = df['Date of Service'].dt.to_period('M')
    
    if 'Service Month' in df.columns:
        df['Service Month'] = df['Service Month'].astype(str)
    
    # Calculate balance if needed
    if all(col in df.columns for col in ['Charge Line Item Amount', 'Total Payments Amount', 'Total Adjustments Amount']):
        if 'Charge Line Item Balance' not in df.columns:
            df['Charge Line Item Balance'] = df['Charge Line Item Amount'] - df['Total Payments Amount'] - df['Total Adjustments Amount']
            
    return df

# -------------------------------------------------------------
# Analytics Functions
# -------------------------------------------------------------
def calculate_kpi_metrics(df):
    """Calculate key KPIs for the dashboard"""
    # Safely calculate metrics, handling potential missing columns
    
    # Total charges
    total_charges = df['Charge Line Item Amount'].sum() if 'Charge Line Item Amount' in df.columns else 0
    
    # Total payments
    total_payments = df['Total Payments Amount'].sum() if 'Total Payments Amount' in df.columns else 0
    
    # Total adjustments
    total_adjustments = df['Total Adjustments Amount'].sum() if 'Total Adjustments Amount' in df.columns else 0
    
    # Collection rate
    collection_rate = (total_payments / total_charges * 100) if total_charges > 0 else 0
    
    # Average days to bill
    avg_days_to_bill = df['Days to Bill'].mean() if 'Days to Bill' in df.columns else 0
    
    # Unbilled/outstanding balance
    outstanding_balance = df['Charge Line Item Balance'].sum() if 'Charge Line Item Balance' in df.columns else 0
    
    # Case volume
    case_volume = len(df['Accession #'].unique()) if 'Accession #' in df.columns else len(df)
    
    return {
        'total_charges': total_charges,
        'total_payments': total_payments,
        'total_adjustments': total_adjustments,
        'collection_rate': collection_rate,
        'avg_days_to_bill': avg_days_to_bill,
        'outstanding_balance': outstanding_balance,
        'case_volume': case_volume
    }

def missing_values_analysis(df):
    """Analyze missing values in the dataset"""
    missing = df.isna().sum().reset_index()
    missing.columns = ['Column', 'Missing Count']
    missing['Missing Percentage'] = (missing['Missing Count'] / len(df) * 100).round(2)
    missing = missing.sort_values('Missing Percentage', ascending=False)
    missing = missing[missing['Missing Percentage'] > 0]
    
    if len(missing) == 0:
        # Create a figure with a message if no missing values
        fig = go.Figure()
        fig.add_annotation(
            text="No missing values found in the dataset!",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(height=500)
        return fig
    
    fig = px.bar(
        missing,
        x='Column',
        y='Missing Percentage',
        title='Missing Values by Column',
        labels={'Missing Percentage': '% Missing', 'Column': 'Column Name'},
        color='Missing Percentage',
        color_continuous_scale='Reds',
        height=500
    )
    fig.update_layout(xaxis={'categoryorder': 'total descending'})
    
    return fig

# -------------------------------------------------------------
# Visualization Functions
# -------------------------------------------------------------
def create_revenue_flow_diagram(df, row_limit=None):
    """Create a Sankey diagram showing revenue flow from charges to final balance"""
    # Use full dataset or limit rows for performance
    sample_df = df.head(row_limit) if row_limit else df
    
    # Calculate flow values
    charges = sample_df['Charge Line Item Amount'].sum() if 'Charge Line Item Amount' in sample_df.columns else 0
    payments = sample_df['Total Payments Amount'].sum() if 'Total Payments Amount' in sample_df.columns else 0
    contractual_adj = sample_df['Total Contractual Adjustment Amount'].sum() if 'Total Contractual Adjustment Amount' in sample_df.columns else 0
    other_adj = sample_df['Total Other Adjustment Amount'].sum() if 'Total Other Adjustment Amount' in sample_df.columns else 0
    balance = sample_df['Charge Line Item Balance'].sum() if 'Charge Line Item Balance' in sample_df.columns else 0
    
    # Check if we have meaningful data to show
    if charges == 0:
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient revenue data to generate flow diagram",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    # Create Sankey diagram
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=["Charges", "Payments", "Contractual Adj", "Other Adj", "Balance"],
            color=["blue", "green", "orange", "red", "gray"]
        ),
        link=dict(
            source=[0, 0, 0, 0],  # Charges
            target=[1, 2, 3, 4],  # To payments, contractual adj, other adj, and balance
            value=[payments, contractual_adj, other_adj, balance],
            color=["rgba(0,255,0,0.4)", "rgba(255,165,0,0.4)", "rgba(255,0,0,0.4)", "rgba(128,128,128,0.4)"]
        )
    )])
    
    fig.update_layout(
        title_text="Revenue Flow Analysis",
        font_size=12,
        height=500
    )
    
    return fig

def create_payment_distribution(df):
    """Create visualization for payment distribution by payer"""
    # Check if necessary columns exist
    if 'Primary Payer Name' not in df.columns or 'Primary Payer Payment Amount' not in df.columns:
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="Missing payer data for distribution analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    # Group by payer and calculate total payments
    payer_payments = df.groupby('Primary Payer Name')['Primary Payer Payment Amount'].sum().reset_index()
    payer_payments = payer_payments.sort_values('Primary Payer Payment Amount', ascending=False)
    
    # Remove any payers with zero or negative payment amounts
    payer_payments = payer_payments[payer_payments['Primary Payer Payment Amount'] > 0]
    
    if len(payer_payments) == 0:
        # Create empty figure with message if no valid data
        fig = go.Figure()
        fig.add_annotation(
            text="No positive payment amounts found for any payer",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    fig = px.pie(
        payer_payments, 
        values='Primary Payer Payment Amount', 
        names='Primary Payer Name',
        title='Payment Distribution by Primary Payer',
        color_discrete_sequence=px.colors.qualitative.Pastel,
        hole=0.4
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=500)
    
    return fig

def create_billing_efficiency_chart(df):
    """Create chart showing billing efficiency (days to bill)"""
    # Check if necessary column exists
    if 'Days to Bill' not in df.columns:
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="Days to Bill data not available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    # Filter out unreasonable values (negative days or > 365 days)
    filtered_df = df[(df['Days to Bill'] >= 0) & (df['Days to Bill'] <= 365)]
    
    if len(filtered_df) == 0:
        # Create empty figure with message if no valid data
        fig = go.Figure()
        fig.add_annotation(
            text="No valid Days to Bill data within reasonable range (0-365 days)",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    # Create histogram of days to bill
    fig = px.histogram(
        filtered_df,
        x='Days to Bill',
        title='Billing Efficiency: Days from Service to Initial Bill',
        labels={'Days to Bill': 'Days', 'count': 'Number of Claims'},
        color_discrete_sequence=['royalblue'],
        nbins=30,
        height=500
    )
    
    # Add a vertical line for average
    mean_days = filtered_df['Days to Bill'].mean()
    fig.add_vline(
        x=mean_days,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Average: {mean_days:.1f} days",
        annotation_position="top right"
    )
    
    # Add vertical line for target (assuming 14 days is a good target)
    fig.add_vline(
        x=14,
        line_dash="dot",
        line_color="green",
        annotation_text="Target: 14 days",
        annotation_position="top left"
    )
    
    return fig

def create_procedure_analysis(df):
    """Create a chart analyzing procedure codes"""
    # Check if necessary columns exist
    required_columns = ['Procedure Code', 'Charge Line Item Amount', 'Total Payments Amount', 'Accession #']
    if not all(col in df.columns for col in required_columns):
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="Missing required columns for procedure analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    try:
        # Aggregate by procedure code
        proc_counts = df.groupby('Procedure Code').agg({
            'Accession #': 'count',
            'Charge Line Item Amount': 'mean',
            'Total Payments Amount': 'mean'
        }).reset_index()
        
        proc_counts.columns = ['Procedure Code', 'Count', 'Avg Charge', 'Avg Payment']
        proc_counts['Collection Rate'] = (proc_counts['Avg Payment'] / proc_counts['Avg Charge'] * 100).round(1)
        proc_counts = proc_counts.sort_values('Count', ascending=False)
        
        # Limit to top 10 procedures by frequency for better visualization
        proc_counts = proc_counts.head(10)
        
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Add bar chart for frequency
        fig.add_trace(
            go.Bar(
                x=proc_counts['Procedure Code'],
                y=proc_counts['Count'],
                name='Frequency',
                marker_color='royalblue'
            )
        )
        
        # Add line chart for collection rate
        fig.add_trace(
            go.Scatter(
                x=proc_counts['Procedure Code'],
                y=proc_counts['Collection Rate'],
                name='Collection Rate %',
                mode='lines+markers',
                marker=dict(size=10, color='crimson'),
                line=dict(width=3, color='crimson')
            ),
            secondary_y=True
        )
        
        # Update layout
        fig.update_layout(
            title='Top Procedure Codes: Frequency vs Collection Rate',
            xaxis_title='Procedure Code',
            height=500
        )
        
        fig.update_yaxes(title_text='Frequency (Count)', secondary_y=False)
        fig.update_yaxes(title_text='Collection Rate (%)', secondary_y=True)
        
        return fig
        
    except Exception as e:
        # If any error occurs, return an empty figure with error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error in procedure analysis: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig

def create_location_revenue_chart(df):
    """Create a chart showing revenue by location"""
    # Check if necessary columns exist
    required_columns = ['Location of Service Name', 'Charge Line Item Amount', 'Total Payments Amount', 'Accession #']
    if not all(col in df.columns for col in required_columns):
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="Missing location or revenue data for analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    try:
        # Group by location
        loc_revenue = df.groupby('Location of Service Name').agg({
            'Charge Line Item Amount': 'sum',
            'Total Payments Amount': 'sum',
            'Accession #': 'count'
        }).reset_index()
        
        loc_revenue.columns = ['Location', 'Total Charges', 'Total Payments', 'Case Count']
        loc_revenue['Collection Rate'] = (loc_revenue['Total Payments'] / loc_revenue['Total Charges'] * 100).round(1)
        loc_revenue = loc_revenue.sort_values('Total Charges', ascending=False)
        
        # Limit to top 10 locations by charge amount for better visualization
        loc_revenue = loc_revenue.head(10)
        
        fig = px.bar(
            loc_revenue,
            x='Location',
            y=['Total Charges', 'Total Payments'],
            title='Revenue by Location',
            barmode='group',
            color_discrete_sequence=['royalblue', 'green'],
            height=500
        )
        
        # Add collection rate as a line
        fig.add_trace(
            go.Scatter(
                x=loc_revenue['Location'],
                y=loc_revenue['Collection Rate'],
                mode='lines+markers',
                name='Collection Rate %',
                yaxis='y2',
                line=dict(color='red', width=3),
                marker=dict(size=10)
            )
        )
        
        # Set up dual y-axis
        fig.update_layout(
            yaxis=dict(title='Amount ($)', side='left'),
            yaxis2=dict(
                title='Collection Rate (%)',
                overlaying='y',
                side='right',
                range=[0, 100]
            ),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        
        return fig
        
    except Exception as e:
        # If any error occurs, return an empty figure with error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error in location revenue analysis: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig

def create_revenue_leakage_analysis(df):
    """Identify and visualize potential revenue leakage points"""
    # Check if necessary columns exist
    required_columns = ['Charge Line Item Amount', 'Total Payments Amount', 'Total Contractual Adjustment Amount']
    if not all(col in df.columns for col in required_columns):
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="Missing data for revenue leakage analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    try:
        # Identify zero payment claims (excluding those with 100% contractual adjustment)
        zero_payment = df[
            (df['Total Payments Amount'] == 0) & 
            (df['Total Contractual Adjustment Amount'] < df['Charge Line Item Amount'])
        ]
        
        # Identify underpayments (assuming collecting less than 70% of remaining balance after adjustments is underpayment)
        potential_underpayment = df[
            (df['Total Payments Amount'] > 0) &
            (df['Total Payments Amount'] < (df['Charge Line Item Amount'] - df['Total Contractual Adjustment Amount']) * 0.7)
        ]
        
        # Create visualization
        categories = ['Zero Payment Claims', 'Potential Underpayments', 'Expected Payment Claims']
        values = [
            len(zero_payment),
            len(potential_underpayment),
            len(df) - len(zero_payment) - len(potential_underpayment)
        ]
        
        # Calculate potential revenue amounts
        zero_payment_amount = zero_payment['Charge Line Item Amount'].sum() - zero_payment['Total Contractual Adjustment Amount'].sum()
        underpayment_amount = potential_underpayment['Charge Line Item Amount'].sum() - potential_underpayment['Total Contractual Adjustment Amount'].sum() - potential_underpayment['Total Payments Amount'].sum()
        
        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "pie"}, {"type": "bar"}]],
            subplot_titles=("Claim Distribution by Payment Status", "Potential Revenue Opportunity")
        )
        
        # Add pie chart
        fig.add_trace(
            go.Pie(
                labels=categories,
                values=values,
                hole=0.4,
                marker_colors=['#FF6B6B', '#FFD166', '#06D6A0']
            ), 
            row=1, col=1
        )
        
        # Add bar chart for dollar amounts
        fig.add_trace(
            go.Bar(
                x=['Zero Payment Opportunity', 'Underpayment Opportunity'],
                y=[zero_payment_amount, underpayment_amount],
                marker_color=['#FF6B6B', '#FFD166']
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            title_text="Revenue Leakage Analysis",
            height=500,
            showlegend=False
        )
        
        return fig
        
    except Exception as e:
        # If any error occurs, return an empty figure with error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error in revenue leakage analysis: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig

def create_denial_analysis(df):
    """Analyze patterns in denied or zero-payment claims"""
    # This is a simplified version - in real implementation, you'd have denial codes
    # For now, we'll use zero payment as a proxy for denial
    
    # Check if necessary columns exist
    required_columns = ['Procedure Code', 'Primary Payer Name', 'Total Payments Amount']
    if not all(col in df.columns for col in required_columns):
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="Missing data for denial analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig
    
    try:
        # Identify zero payment claims
        zero_payment = df[df['Total Payments Amount'] == 0]
        
        if len(zero_payment) == 0:
            # Create empty figure with message if no zero payments
            fig = go.Figure()
            fig.add_annotation(
                text="No denied/zero-payment claims found for analysis",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16)
            )
            fig.update_layout(height=500)
            return fig
        
        # Create heatmap of zero payments by procedure and payer
        denial_heatmap = pd.crosstab(
            zero_payment['Procedure Code'], 
            zero_payment['Primary Payer Name'],
            normalize='all'
        ) * 100  # Convert to percentage
        
        # Create heatmap
        fig = px.imshow(
            denial_heatmap,
            x=denial_heatmap.columns,
            y=denial_heatmap.index,
            color_continuous_scale='Reds',
            title='Zero Payment Claims Distribution by Procedure and Payer (%)',
            labels=dict(x='Primary Payer', y='Procedure Code', color='% of Zero Payments')
        )
        
        fig.update_layout(height=500)
        
        return fig
        
    except Exception as e:
        # If any error occurs, return an empty figure with error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error in denial analysis: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=500)
        return fig

# -------------------------------------------------------------
# SVG for Revenue Cycle Workflow Diagram
# -------------------------------------------------------------

# SVG representation of the revenue cycle workflow
def get_workflow_svg():
    """Return the SVG for the revenue cycle workflow diagram"""
    svg = '''
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500">
      <!-- Background -->
      <rect width="800" height="500" fill="#f8f9fa" rx="10" ry="10"/>
      
      <!-- Title -->
      <text x="400" y="30" font-family="Arial" font-size="20" text-anchor="middle" font-weight="bold" fill="#333">Versant Diagnostics: Anatomic Pathology Revenue Cycle Workflow</text>
      
      <!-- Workflow steps with arrows -->
      <!-- Step 1 -->
      <rect x="50" y="70" width="160" height="70" rx="10" ry="10" fill="#e6f2ff" stroke="#0066cc" stroke-width="2"/>
      <text x="130" y="95" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Sample Collection</text>
      <text x="130" y="115" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">Specimen accessioning</text>
      <text x="130" y="130" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">Accession # assigned</text>
      
      <!-- Arrow 1 -->
      <path d="M210 105 L240 105" stroke="#555" stroke-width="2" fill="none"/>
      <polygon points="240,105 235,102 235,108" fill="#555"/>
      
      <!-- Step 2 -->
      <rect x="240" y="70" width="160" height="70" rx="10" ry="10" fill="#e6f2ff" stroke="#0066cc" stroke-width="2"/>
      <text x="320" y="95" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Pathology Services</text>
      <text x="320" y="115" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">Digital diagnosis</text>
      <text x="320" y="130" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">By sub-specialized pathologists</text>
      
      <!-- Arrow 2 -->
      <path d="M400 105 L430 105" stroke="#555" stroke-width="2" fill="none"/>
      <polygon points="430,105 425,102 425,108" fill="#555"/>
      
      <!-- Step 3 -->
      <rect x="430" y="70" width="160" height="70" rx="10" ry="10" fill="#e6f2ff" stroke="#0066cc" stroke-width="2"/>
      <text x="510" y="95" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Documentation</text>
      <text x="510" y="115" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">Procedure and diagnosis coding</text>
      <text x="510" y="130" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">CPT, ICD-10, modifiers</text>
      
      <!-- Arrow 3 -->
      <path d="M590 105 L620 105" stroke="#555" stroke-width="2" fill="none"/>
      <polygon points="620,105 615,102 615,108" fill="#555"/>
      
      <!-- Step 4 -->
      <rect x="620" y="70" width="160" height="70" rx="10" ry="10" fill="#e6f2ff" stroke="#0066cc" stroke-width="2"/>
      <text x="700" y="95" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Charge Capture</text>
      <text x="700" y="115" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">LIS integration</text>
      <text x="700" y="130" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">Charge generation</text>
      
      <!-- Arrow 4 - connecting to next row -->
      <path d="M700 140 L700 160 L130 160 L130 180" stroke="#555" stroke-width="2" fill="none"/>
      <polygon points="130,180 127,175 133,175" fill="#555"/>
      
      <!-- Step 5 - Second row -->
      <rect x="50" y="180" width="160" height="70" rx="10" ry="10" fill="#fff0e6" stroke="#cc6600" stroke-width="2"/>
      <text x="130" y="205" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Claims Submission</text>
      <text x="130" y="225" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">To primary and secondary payers</text>
      <text x="130" y="240" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">Date of Initial Bill</text>
      
      <!-- Arrow 5 -->
      <path d="M210 215 L240 215" stroke="#555" stroke-width="2" fill="none"/>
      <polygon points="240,215 235,212 235,218" fill="#555"/>
      
      <!-- Step 6 -->
      <rect x="240" y="180" width="160" height="70" rx="10" ry="10" fill="#fff0e6" stroke="#cc6600" stroke-width="2"/>
      <text x="320" y="205" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Payment Processing</text>
      <text x="320" y="225" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">Insurance and patient payments</text>
      <text x="320" y="240" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">Payment amounts tracked</text>
      
      <!-- Arrow 6 -->
      <path d="M400 215 L430 215" stroke="#555" stroke-width="2" fill="none"/>
      <polygon points="430,215 425,212 425,218" fill="#555"/>
      
      <!-- Step 7 -->
      <rect x="430" y="180" width="160" height="70" rx="10" ry="10" fill="#fff0e6" stroke="#cc6600" stroke-width="2"/>
      <text x="510" y="205" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Adjustments</text>
      <text x="510" y="225" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">Contractual and other adjustments</text>
      <text x="510" y="240" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">Negotiated reductions</text>
      
      <!-- Arrow 7 -->
      <path d="M590 215 L620 215" stroke="#555" stroke-width="2" fill="none"/>
      <polygon points="620,215 615,212 615,218" fill="#555"/>
      
      <!-- Step 8 -->
      <rect x="620" y="180" width="160" height="70" rx="10" ry="10" fill="#fff0e6" stroke="#cc6600" stroke-width="2"/>
      <text x="700" y="205" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Revenue Analysis</text>
      <text x="700" y="225" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">Uncollected revenue recovery</text>
      <text x="700" y="240" font-family="Arial" font-size="11" text-anchor="middle" fill="#666">Balance management</text>
      
      <!-- Data Metrics Section -->
      <rect x="50" y="300" width="730" height="150" rx="10" ry="10" fill="#f0f0f0" stroke="#888" stroke-width="2"/>
      <text x="400" y="325" font-family="Arial" font-size="16" text-anchor="middle" font-weight="bold" fill="#333">Key Revenue Cycle Metrics and Analysis Points</text>
      
      <!-- Metrics columns -->
      <!-- Column 1 -->
      <text x="130" y="350" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Volume Metrics</text>
      <text x="130" y="370" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Case volume by location</text>
      <text x="130" y="390" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Procedure code frequency</text>
      <text x="130" y="410" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Provider productivity</text>
      
      <!-- Column 2 -->
      <text x="320" y="350" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Financial Metrics</text>
      <text x="320" y="370" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Charges vs. collections</text>
      <text x="320" y="390" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Adjustment rates</text>
      <text x="320" y="410" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Collection rate by payer</text>
      
      <!-- Column 3 -->
      <text x="510" y="350" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Efficiency Metrics</text>
      <text x="510" y="370" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Days to initial bill</text>
      <text x="510" y="390" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Lag time analysis</text>
      <text x="510" y="410" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Clean claim rate</text>
      
      <!-- Column 4 -->
      <text x="700" y="350" font-family="Arial" font-size="14" text-anchor="middle" font-weight="bold" fill="#333">Revenue Opportunities</text>
      <text x="700" y="370" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Unbilled cases</text>
      <text x="700" y="390" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Denial patterns</text>
      <text x="700" y="410" font-family="Arial" font-size="12" text-anchor="middle" fill="#555">• Underpaid claims</text>
      
      <!-- Versant logo placeholder -->
      <text x="400" y="460" font-family="Arial" font-size="12" text-anchor="middle" font-style="italic" fill="#666">Versant Diagnostics: Transforming Patient Care Through Innovation in Digital Anatomic Pathology</text>
    </svg>
    '''
    return svg

# -------------------------------------------------------------
# Main Application
# -------------------------------------------------------------

def main():
    """Main function to run the Streamlit application"""
    # Application title and description
    st.title("Versant Diagnostics Revenue Cycle Analysis")
    st.markdown("""
    This dashboard provides comprehensive analysis of revenue cycle metrics for anatomic pathology services.
    Upload your data file or use sample data to explore key financial insights.
    """)
    
    # Sidebar for data loading options
    st.sidebar.title("Data Source")
    data_source = st.sidebar.radio(
        "Select data source:",
        ["Upload Excel File", "Use Sample Data"]
    )
    
    # Initialize dataframe
    df = pd.DataFrame()
    
    # Upload file widget - moved outside cached function
    uploaded_file = None
    if data_source == "Upload Excel File":
        uploaded_file = st.sidebar.file_uploader(
            "Upload Excel or CSV file", 
            type=["xlsx", "xls", "csv"],
            help="Upload your revenue cycle data file in Excel or CSV format"
        )
    
    # Load data based on selection
    if data_source == "Upload Excel File" and uploaded_file is not None:
        df = load_data_from_upload(uploaded_file)
    elif data_source == "Use Sample Data" and st.sidebar.button("Generate Sample Data"):
        df = create_sample_data()
        st.sidebar.success("Sample data generated!")
    
    # Process data if available
    if not df.empty:
        df = preprocess_data(df)
        
        # Display data info in sidebar
        st.sidebar.subheader("Dataset Information")
        st.sidebar.info(f"Total records: {len(df)}")
        st.sidebar.info(f"Date range: {df['Date of Service'].min().date()} to {df['Date of Service'].max().date()}" 
                      if 'Date of Service' in df.columns else "Date information not available")
        
        # Calculate KPIs
        kpis = calculate_kpi_metrics(df)
        
        # Display KPIs in the main area
        st.subheader("Key Performance Indicators")
        
        # Create 4 columns for KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Charges", 
                f"${kpis['total_charges']:,.2f}", 
                delta=None
            )
            st.metric(
                "Case Volume", 
                f"{int(kpis['case_volume']):,}", 
                delta=None
            )
        
        with col2:
            st.metric(
                "Total Payments", 
                f"${kpis['total_payments']:,.2f}", 
                delta=None
            )
            st.metric(
                "Outstanding Balance", 
                f"${kpis['outstanding_balance']:,.2f}", 
                delta=None
            )
        
        with col3:
            st.metric(
                "Collection Rate", 
                f"{kpis['collection_rate']:.1f}%", 
                delta=None
            )
            st.metric(
                "Total Adjustments", 
                f"${kpis['total_adjustments']:,.2f}", 
                delta=None
            )
        
        with col4:
            st.metric(
                "Avg Days to Bill", 
                f"{kpis['avg_days_to_bill']:.1f}", 
                delta=None
            )
            # Add a button to display the revenue cycle workflow
            if st.button("View Revenue Cycle Workflow"):
                st.markdown(get_workflow_svg(), unsafe_allow_html=True)
        
        # Tabs for different analyses
        tab1, tab2, tab3, tab4 = st.tabs([
            "Revenue Analysis", "Billing Efficiency", "Payer Analysis", "Data Quality"
        ])
        
        with tab1:
            st.subheader("Revenue Flow Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                st.plotly_chart(create_revenue_flow_diagram(df), use_container_width=True)
            
            with col2:
                st.plotly_chart(create_procedure_analysis(df), use_container_width=True)
            
            st.subheader("Revenue by Location")
            st.plotly_chart(create_location_revenue_chart(df), use_container_width=True)
            
            st.subheader("Revenue Leakage Analysis")
            st.plotly_chart(create_revenue_leakage_analysis(df), use_container_width=True)
        
        with tab2:
            st.subheader("Billing Efficiency Metrics")
            st.plotly_chart(create_billing_efficiency_chart(df), use_container_width=True)
            
            # Additional billing efficiency metrics could be added here
            col1, col2 = st.columns(2)
            
            with col1:
                # Display average days between service and entry
                if all(col in df.columns for col in ['Date of Service', 'Date of Entry']):
                    avg_entry_days = (df['Date of Entry'] - df['Date of Service']).dt.days.mean()
                    st.metric("Avg Days: Service to Entry", f"{avg_entry_days:.1f}", delta=None)
            
            with col2:
                # Display average days between entry and billing
                if all(col in df.columns for col in ['Date of Entry', 'Date of Initial Bill']):
                    avg_entry_to_bill = (df['Date of Initial Bill'] - df['Date of Entry']).dt.days.mean()
                    st.metric("Avg Days: Entry to Bill", f"{avg_entry_to_bill:.1f}", delta=None)
        
        with tab3:
            st.subheader("Payer Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                st.plotly_chart(create_payment_distribution(df), use_container_width=True)
            
            with col2:
                st.plotly_chart(create_denial_analysis(df), use_container_width=True)
            
            # If we have payer and collection rate data, display table
            if all(col in df.columns for col in ['Primary Payer Name', 'Charge Line Item Amount', 'Total Payments Amount']):
                st.subheader("Collection Rate by Payer")
                
                payer_stats = df.groupby('Primary Payer Name').agg({
                    'Charge Line Item Amount': 'sum',
                    'Total Payments Amount': 'sum',
                    'Accession #': 'count'
                }).reset_index()
                
                payer_stats.columns = ['Payer', 'Total Charges', 'Total Payments', 'Claim Count']
                payer_stats['Collection Rate (%)'] = (payer_stats['Total Payments'] / payer_stats['Total Charges'] * 100).round(1)
                payer_stats = payer_stats.sort_values('Collection Rate (%)', ascending=False)
                
                # Format currency columns
                payer_stats['Total Charges'] = payer_stats['Total Charges'].apply(lambda x: f"${x:,.2f}")
                payer_stats['Total Payments'] = payer_stats['Total Payments'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(payer_stats, use_container_width=True)
        
        with tab4:
            st.subheader("Data Quality Analysis")
            st.plotly_chart(missing_values_analysis(df), use_container_width=True)
            
            # Display data preview with option to download
            st.subheader("Data Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Create a download button for the data
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Full Dataset as CSV",
                data=csv,
                file_name="versant_revenue_data.csv",
                mime="text/csv",
            )
    else:
        # Display welcome message and instructions if no data is loaded
        st.info("👈 Please select a data source from the sidebar to get started.")
        
        # Show workflow diagram
        st.subheader("Revenue Cycle Workflow")
        st.markdown(get_workflow_svg(), unsafe_allow_html=True)
        
        st.markdown("""
        ### About This Dashboard
        
        This revenue cycle analytics dashboard provides comprehensive insights into anatomic pathology billing and collections. Key features include:
        
        - **Revenue Analysis**: Visualize revenue flow, procedure profitability, and location performance
        - **Billing Efficiency**: Track days to bill and identify bottlenecks in the billing process
        - **Payer Analysis**: Analyze payment patterns and collection rates by payer
        - **Data Quality**: Identify missing data and potential data quality issues
        
        To begin, upload your Excel data file or generate sample data using the options in the sidebar.
        """)

if __name__ == "__main__":
    main()
