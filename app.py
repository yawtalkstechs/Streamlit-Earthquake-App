import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Set page config
st.set_page_config(
    page_title="Earthquake Data Explorer",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("🌍 Earthquake Data Explorer")
st.markdown("Real-time earthquake data from the USGS Earthquake Hazards Program")

# Sidebar for parameters
st.sidebar.header("Filter Parameters")

# Time range selection
time_options = {
    "Past Hour": "hour",
    "Past Day": "day", 
    "Past 7 Days": "week",
    "Past 30 Days": "month"
}
selected_time = st.sidebar.selectbox("Time Range:", list(time_options.keys()), index=2)

# Magnitude filter
magnitude_options = {
    "All Earthquakes": "all",
    "Significant Earthquakes": "significant",
    "M4.5+ Earthquakes": "4.5",
    "M2.5+ Earthquakes": "2.5",
    "M1.0+ Earthquakes": "1.0"
}
selected_magnitude = st.sidebar.selectbox("Magnitude:", list(magnitude_options.keys()), index=2)

# Maximum number of results
max_results = st.sidebar.slider("Maximum Results:", min_value=10, max_value=1000, value=100, step=10)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_earthquake_data(time_period, magnitude, limit):
    """Fetch earthquake data from USGS API"""
    
    # Build API URL
    base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    
    params = {
        "format": "geojson",
        "limit": limit,
        "orderby": "time"
    }
    
    # Add time parameter
    if time_period != "all":
        params["starttime"] = (datetime.now() - timedelta(days=30 if time_period == "month" else 7 if time_period == "week" else 1 if time_period == "day" else 1/24)).isoformat()
    
    # Add magnitude parameter
    if magnitude != "all" and magnitude != "significant":
        params["minmagnitude"] = float(magnitude)
    elif magnitude == "significant":
        # For significant earthquakes, we'll filter after fetching
        pass
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

def process_earthquake_data(data):
    """Process the earthquake data into a pandas DataFrame"""
    if not data or 'features' not in data:
        return pd.DataFrame()
    
    earthquakes = []
    for feature in data['features']:
        props = feature['properties']
        coords = feature['geometry']['coordinates']
        
        earthquake = {
            'magnitude': props.get('mag'),
            'place': props.get('place'),
            'time': datetime.fromtimestamp(props.get('time', 0) / 1000),
            'longitude': coords[0] if len(coords) > 0 else None,
            'latitude': coords[1] if len(coords) > 1 else None,
            'depth': coords[2] if len(coords) > 2 else None,
            'url': props.get('url'),
            'tsunami': props.get('tsunami', 0),
            'significance': props.get('sig', 0),
            'alert': props.get('alert'),
            'felt': props.get('felt', 0),
            'cdi': props.get('cdi'),
            'mmi': props.get('mmi')
        }
        earthquakes.append(earthquake)
    
    df = pd.DataFrame(earthquakes)
    
    # Filter out rows with missing magnitude or coordinates
    df = df.dropna(subset=['magnitude', 'longitude', 'latitude'])
    
    # Filter for significant earthquakes if selected
    if selected_magnitude == "Significant Earthquakes":
        df = df[df['significance'] >= 600]  # USGS threshold for significant earthquakes
    
    return df

# Fetch and process data
with st.spinner("Fetching earthquake data..."):
    earthquake_data = fetch_earthquake_data(
        time_options[selected_time], 
        magnitude_options[selected_magnitude], 
        max_results
    )

if earthquake_data:
    df = process_earthquake_data(earthquake_data)
    
    if not df.empty:
        # Display summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Earthquakes", len(df))
        
        with col2:
            st.metric("Largest Magnitude", f"{df['magnitude'].max():.1f}")
        
        with col3:
            avg_mag = df['magnitude'].mean()
            st.metric("Average Magnitude", f"{avg_mag:.1f}")
        
        with col4:
            recent_count = len(df[df['time'] > datetime.now() - timedelta(hours=24)])
            st.metric("Last 24 Hours", recent_count)
        
        # Create tabs for different visualizations
        tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Map", "📊 Charts", "📋 Data Table", "ℹ️ Details"])
        
        with tab1:
            st.subheader("Earthquake Locations")
            
            # Create map visualization
            if not df.empty:
                fig = px.scatter_mapbox(
                    df, 
                    lat="latitude", 
                    lon="longitude",
                    size="magnitude",
                    color="magnitude",
                    hover_name="place",
                    hover_data={
                        "magnitude": True,
                        "depth": ":.1f",
                        "time": True,
                        "latitude": ":.3f",
                        "longitude": ":.3f"
                    },
                    color_continuous_scale="Reds",
                    size_max=20,
                    zoom=1,
                    mapbox_style="open-street-map",
                    title="Earthquake Locations and Magnitudes"
                )
                
                fig.update_layout(
                    height=600,
                    margin={"r":0,"t":50,"l":0,"b":0}
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader("Earthquake Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Magnitude distribution
                fig_hist = px.histogram(
                    df, 
                    x="magnitude", 
                    nbins=30,
                    title="Magnitude Distribution",
                    labels={'magnitude': 'Magnitude', 'count': 'Number of Earthquakes'}
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            
            with col2:
                # Depth vs Magnitude scatter plot
                fig_scatter = px.scatter(
                    df, 
                    x="depth", 
                    y="magnitude",
                    hover_name="place",
                    title="Depth vs Magnitude",
                    labels={'depth': 'Depth (km)', 'magnitude': 'Magnitude'}
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
            
            # Timeline
            st.subheader("Earthquake Timeline")
            df_sorted = df.sort_values('time')
            fig_timeline = px.scatter(
                df_sorted, 
                x="time", 
                y="magnitude",
                size="magnitude",
                hover_name="place",
                title="Earthquakes Over Time",
                labels={'time': 'Time', 'magnitude': 'Magnitude'}
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
        
        with tab3:
            st.subheader("Earthquake Data Table")
            
            # Format the dataframe for display
            display_df = df.copy()
            display_df['time'] = display_df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
            display_df = display_df.round({'magnitude': 2, 'latitude': 4, 'longitude': 4, 'depth': 1})
            
            # Select columns to display
            columns_to_show = ['time', 'magnitude', 'place', 'latitude', 'longitude', 'depth', 'tsunami']
            display_df = display_df[columns_to_show]
            
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "time": "Time (UTC)",
                    "magnitude": st.column_config.NumberColumn("Magnitude", format="%.1f"),
                    "place": "Location",
                    "latitude": st.column_config.NumberColumn("Latitude", format="%.4f"),
                    "longitude": st.column_config.NumberColumn("Longitude", format="%.4f"),
                    "depth": st.column_config.NumberColumn("Depth (km)", format="%.1f"),
                    "tsunami": st.column_config.CheckboxColumn("Tsunami Warning")
                }
            )
            
            # Download button
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"earthquake_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with tab4:
            st.subheader("Earthquake Details")
            
            if not df.empty:
                # Find the largest earthquake
                largest_eq = df.loc[df['magnitude'].idxmax()]
                
                st.write("**Largest Earthquake in Dataset:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Magnitude:** {largest_eq['magnitude']}")
                    st.write(f"**Location:** {largest_eq['place']}")
                    st.write(f"**Time:** {largest_eq['time']}")
                
                with col2:
                    st.write(f"**Coordinates:** {largest_eq['latitude']:.3f}, {largest_eq['longitude']:.3f}")
                    st.write(f"**Depth:** {largest_eq['depth']:.1f} km")
                    if largest_eq['url']:
                        st.write(f"**[More Info]({largest_eq['url']})**")
                
                # Additional statistics
                st.subheader("Statistical Summary")
                st.write(df[['magnitude', 'depth', 'significance']].describe())
                
    else:
        st.warning("No earthquake data found for the selected criteria.")
        
else:
    st.error("Failed to fetch earthquake data. Please check your internet connection and try again.")

# Footer
st.markdown("---")
st.markdown("Data source: [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/)")
st.markdown("*Data is updated in real-time from USGS feeds*")