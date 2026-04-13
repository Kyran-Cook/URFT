import streamlit as st
from datetime import date
import universal_transform as ut
import io
from contextlib import redirect_stdout, redirect_stderr
import pandas as pd
import pydeck as pdk
import json

# ----------------------------
# Constants
# ----------------------------
STATIC_FRAMES = [
    "GDA2020", "GDA94", "AGD66", "AGD84", "MGA94", "MGA2020"
]

DYNAMIC_FRAMES = [
    "ATRF2014",
    "ITRF88", "ITRF89", "ITRF90", "ITRF91", "ITRF92", "ITRF93", "ITRF94",
    "ITRF96", "ITRF97", "ITRF2000", "ITRF2005", "ITRF2008", "ITRF2014",
    "ITRF2020",
    "WGS84 (Transit)", "WGS84 (G730)", "WGS84 (G873)", "WGS84 (G1150)",
    "WGS84 (G1674)", "WGS84 (G1762)", "WGS84 (G2139)", "WGS84 (G2296)",
    "WGS84 Ensemble"
]

ALL_FRAMES = STATIC_FRAMES + DYNAMIC_FRAMES
COORD_TYPES = ["XYZ", "LLH", "ENU"]
EPOCH_FORMATS = ["Decimal year", "YYYY-MM-DD"]

DEFAULTS = {
    # Frames
    "from_frame": "GDA2020",
    "to_frame": "ITRF2014",  # matches your current default index

    # Epochs (your date_input uses date objects or None)
    "from_epoch": date(2020, 1, 1),
    "to_epoch": date(2020, 1, 1),

    # Input coordinate type + helper
    "input_type": "XYZ",
    "input_type_last_non_mga": "XYZ",

    # Output coordinate type + helper
    "output_type": "XYZ",
    "output_type_last_non_mga": "XYZ",

    # LLH notation
    "llh_type": "Decimal Degrees",

    # XYZ
    "x": None,
    "y": None,
    "z": None,

    # llh

}

for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

def reset_all():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v

def is_dynamic(frame: str) -> bool:
    return frame in DYNAMIC_FRAMES


def parse_float(s: str):
    try:
        return float(s)
    except Exception:
        return None


def swap_frames():
    # Swap current values
    st.session_state["from_frame"], st.session_state["to_frame"] = (
        st.session_state.get("to_frame"),
        st.session_state.get("from_frame"),
    )
    st.session_state["to_epoch"], st.session_state["from_epoch"] = (
        st.session_state["from_epoch"],
        st.session_state["to_epoch"],
    )


# ----------------------------
# Streamlit page config
# ----------------------------
st.set_page_config(
    page_title="Universal Transformation Calculator",
    page_icon="🌐",
    layout="wide"
)

st.logo("geodepy-logo-light.png", size="large")

st.title("Universal Reference Frame Transformation")
st.caption(
    "This tool will let you transform from any reference frame to any other reference frame. "
)
# ----------------------------
# Layout
# ----------------------------
left, right = st.columns([0.55, 0.45], gap="large")

with left:
    st.subheader("Inputs")

    # --- Frame selection
    c1, c2, c3 = st.columns([0.46, 0.08, 0.46])
    with c1:
        from_frame = st.selectbox(
            "From reference frame",
            options=ALL_FRAMES,
            index=0,  # default GDA2020
            key="from_frame"
        )
    with c2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.button("⇄", help="Swap From/To frames", on_click=swap_frames)
    with c3:
        to_frame = st.selectbox(
            "To reference frame",
            options=ALL_FRAMES,
            key="to_frame"
        )



    dynamic_required = is_dynamic(from_frame) or is_dynamic(to_frame)

    if dynamic_required:
        st.info("Dynamic frame selected — an epoch is required.")

    # --- Epoch input
    coord_epoch = None
    target_epoch = None
    from_epoch_required = False
    to_epoch_required = False

    if dynamic_required:
        st.markdown("### Epoch")
        c1, c2, c3 = st.columns([0.46, 0.08, 0.46])
        with c1:
            from_epoch_required = is_dynamic(from_frame)
            coord_epoch = st.date_input(
                "From epoch (date)", 
                value=date(2020,1,1) if from_epoch_required else None,
                format="YYYY-MM-DD",
                disabled=not from_epoch_required,
                min_value=date(1900,1,1),
                max_value=date.today(), 
                help="Click to open calendar.",
                key="from_epoch")

        with c3:
            to_epoch_required = is_dynamic(to_frame)
            target_epoch = st.date_input(
                "To epoch (date)", 
                #value=date(2020,1,1) if to_epoch_required else None,
                format="YYYY-MM-DD", 
                disabled=not to_epoch_required,
                min_value=date(1900,1,1),
                max_value=date.today(), 
                help="Click to open calendar.",
                key="to_epoch")
                        
    else:
        st.caption("Epoch not required when both frames are static.")

    st.divider()

    # --- Input / Output coordinate type

    st.markdown("### Input Coordinate Type")

    # Automatically change to enu if MGA is chosen
    from_enu_needed = from_frame in ("MGA94", "MGA2020")

    if "input_type" not in st.session_state:
        st.session_state["input_type"] = "XYZ"

    if "input_type_last_non_mga" not in st.session_state:
        st.session_state["input_type_last_non_mga"] = st.session_state["input_type"]

    # If MGA in from_frame save last input_type and change to ENU
    if from_enu_needed:
        if st.session_state["input_type"] != "ENU":
            st.session_state["input_type_last_non_mga"] = st.session_state["input_type"]
            st.session_state["input_type"] = "ENU"
    
    # If not MGA change back to last saved input_type
    else:
        if st.session_state["input_type"] == "ENU":
            st.session_state["input_type"] = st.session_state["input_type_last_non_mga"]
            st.info("Can't select ENU when not using MGA as from reference frame.")

    # Control for what input type
    input_type = st.segmented_control(
        "Input coordinate type",
        ["XYZ", "LLH", "ENU"],
        label_visibility="collapsed",
        selection_mode="single",
        default=st.session_state["input_type"],
        disabled=from_enu_needed,
        width="stretch",
        key="input_type"
    )

    st.markdown("### Coordinate input")

    # --- Coordinate input panels
    xyz = llh = enu = None

    if input_type == "XYZ":
        cx, cy, cz = st.columns(3)
        with cx:
            x = st.text_input("X (m)", placeholder="-4052052.12", key="x")
        with cy:
            y = st.text_input("Y (m)", placeholder="4212834.56", key="y")
        with cz:
            z = st.text_input("Z (m)", placeholder="-2545100.78", key="z")
        try:
            xyz = {"x": float(x), "y": float(y), "z": float(z)}
        except:
            pass

    elif input_type == "LLH":

        llh_type = st.segmented_control(
            "Coordinate Notation",
            ["Decimal Degrees", "Degrees Minutes Seconds", "Degrees Decimal Minutes"],
            selection_mode="single",
            default="Decimal Degrees",
            width="stretch",
            key="llh_type"
        )
        st.caption("Use - for South, + for North.")

        if llh_type == "Decimal Degrees":
            c8, c9 = st.columns(2)
            with c8:
                lat = st.text_input("Latitude", placeholder="-35.2809", key="lat")
            with c9:
                lon = st.text_input("Longitude", placeholder="149.1300", key="lon")
            h = st.text_input("Ellipsoidal height (m)", placeholder="575.34", key="height")
            try:
                llh = {"lat": float(lat), "lon": float(lon), "h": float(h), "lat_format": llh_type}
            except:
                pass

        if llh_type == "Degrees Minutes Seconds":
            c8, c9, c10 = st.columns(3)
            with c8:
                lat_deg = st.text_input("Latitude", placeholder="-35", key="lat_deg")
                lon_deg = st.text_input("Longitude", placeholder="149", key="lon_deg")
            with c9:
                lat_min = st.text_input("Latitude", placeholder="28", label_visibility="hidden", key="lat_min")
                lon_min = st.text_input("Longitude", placeholder="13", label_visibility="hidden", key="lon_min")
            with c10:
                lat_sec = st.text_input("Latitude", placeholder="09", label_visibility="hidden", key="lat_sec")
                lon_sec = st.text_input("Longitude", placeholder="21", label_visibility="hidden", key="lon_sec")
            h = st.text_input("Ellipsoidal height (m)", placeholder="575.34", key="height_dms")
            
            try:
                lat = float(lat_deg) + float(lat_min)/60 + float(lat_sec)/3600
                lon = float(lon_deg) + float(lon_min)/60 + float(lon_sec)/3600
                llh = {"lat": lat, "lon": lon, "h": float(h), "lat_format": llh_type}
            except:
                pass
            
        if llh_type == "Degrees Decimal Minutes":
            c8, c9 = st.columns(2)
            with c8:
                lat_deg = st.text_input("Latitude", placeholder="-35")
                lon_deg = st.text_input("Longitude", placeholder="149")
            with c9:
                lat_min = st.text_input("Latitude", placeholder="28.09", label_visibility="hidden")
                lon_min = st.text_input("Longitude", placeholder="13.21", label_visibility="hidden")
            h = st.text_input("Ellipsoidal height (m)", placeholder="575.34")
            try:
                lat = float(lat_deg) + float(lat_min)/60
                lon = float(lon_deg) + float(lon_min)/60
                llh = {"lat": float(lat), "lon": float(lon), "h": float(h), "lat_format": llh_type}
            except:
                pass

    else:  # ENU
        ce, cn, cu = st.columns(3)
        with ce:
            e = st.text_input("Easting (m)", placeholder="12.345")
            zone = st.text_input("Zone (1-60)", placeholder="55")
        with cn:
            n = st.text_input("Northing (m)", placeholder="-6.789")
        with cu:
            u = st.text_input("Up (m)", placeholder="1.234")
        try:
            enu = {"e": float(e), "n": float(n), "u": float(u), "zone": int(zone)}
        except:
            pass

    # --- Output options
    st.divider()
    st.markdown("### Coordinate input")

    # Automatically change to enu if MGA is chosen
    to_enu_needed = to_frame in ("MGA94", "MGA2020")

    if "output_type" not in st.session_state:
        st.session_state["output_type"] = "XYZ"

    if "output_type_last_non_mga" not in st.session_state:
        st.session_state["output_type_last_non_mga"] = st.session_state["output_type"]

    # If MGA in from_frame save last input_type and change to ENU
    if to_enu_needed:
        if st.session_state["output_type"] != "ENU":
            st.session_state["output_type_last_non_mga"] = st.session_state["output_type"]
            st.session_state["output_type"] = "ENU"
    
    # If not MGA change back to last saved input_type
    else:
        if st.session_state["output_type"] == "ENU":
            st.session_state["output_type"] = st.session_state["output_type_last_non_mga"]
            st.info("Can't select ENU when not using MGA as to reference frame.")

    # Control for what input type
    output_type = st.segmented_control(
        "Output coordinate type",
        ["XYZ", "LLH", "ENU"],
        label_visibility="collapsed",
        selection_mode="single",
        default=st.session_state["output_type"],
        disabled=to_enu_needed,
        width="stretch",
        key="output_type"
    )

    # --- Transform button
    st.divider()

    crun, creset = st.columns([0.1, 0.8])
    with crun:
        run = st.button("Transform", type="primary")
    with creset:
        st.button("Reset to defaults", type="secondary", on_click=reset_all)


with right:
    st.subheader("Output")

    if not run:
        st.write("Run a transformation to see results.")
        st.caption(
            "This panel will show: transformed coordinates, transforomation path and a map showing the point location."
        )

    else:
        # Basic validation warnings (lightweight)
        errors = []

        if dynamic_required and coord_epoch is None:
            errors.append("Coordinate epoch is required for dynamic frames.")

        if errors:
            st.error("Cannot run transformation:\n- " + "\n- ".join(errors))
        else:
            # Placeholder result formatting (wire this to your real engine)

            st.markdown("#### Summary")
            if from_epoch_required:
                st.write(f"**From:** {from_frame} at {coord_epoch}")
            else:
                st.write(f"**From:** {from_frame}")                
            
            if to_epoch_required:
                st.write(f"**To:** {to_frame} at {target_epoch}")
            else:
                st.write(f"**To:** {to_frame}")

            if target_epoch:
                map_epoch = target_epoch
            else:
                map_epoch = date(2020,1,1)


            if input_type == "XYZ":
                map_result = ut.universal_transform(xyz["x"], xyz["y"], xyz["z"], from_frame, "WGS84 Ensemble", coord_epoch, map_epoch, "auto", None, "llh", True)
            elif input_type == "LLH":
                map_result = ut.universal_transform_llh(llh["lat"], llh["lon"], llh["h"], from_frame, "WGS84 Ensemble", coord_epoch, map_epoch, "auto", None, "llh", True)
            elif input_type == "ENU":
                map_result = ut.universal_transform_enu(enu["e"], enu["n"], enu["u"], enu["zone"], from_frame, "WGS84 Ensemble", coord_epoch, map_epoch, "auto", None, "llh", True)

            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                try:
                    if input_type == "XYZ":
                        result = ut.universal_transform(xyz["x"], xyz["y"], xyz["z"], from_frame, to_frame, coord_epoch, target_epoch, "aus", None, output_type)
                    elif input_type == "LLH":
                        result = ut.universal_transform_llh(llh["lat"], llh["lon"], llh["h"], from_frame, to_frame, coord_epoch, target_epoch, "aus", None, output_type)
                    elif input_type == "ENU":
                        result = ut.universal_transform_enu(enu["e"], enu["n"], enu["u"], enu["zone"], from_frame, to_frame, coord_epoch, target_epoch, "aus", None, output_type)
                except Exception as e:
                    st.error(f"Error during transformation: {e}")
                    result = None
            printed_output = buf.getvalue()
            
            st.markdown("#### Path")
            st.code(
                f"{printed_output}",
                language="text",
            )

            st.markdown("#### Result")
            try:
                if output_type == "XYZ":
                    result_str = f"X: {result['coords']['x']} m\nY: {result['coords']['y']} m\nZ: {result['coords']['z']} m"
                elif output_type == "LLH":
                    result_str = f"Latitude: {result['coords']['lat']}°\nLongitude: {result['coords']['lon']}°\nEllipsoidal Height: {result['coords']['el_height']} m"
                elif output_type == "ENU":
                    result_str = f"Easting: {result['coords']['east']} m\nNorthing: {result['coords']['north']} m\nUp: {result['coords']['height']} m\nZone: {result['coords']['zone']}"
                st.code(
                    f"{result_str}",
                    language="text",
                )
                st.success("Transformation complete!")
            except:
                pass

            df = pd.DataFrame({
                "lat": [map_result["coords"]["lat"]],
                "lon": [map_result["coords"]["lon"]],
                "label": ["Transformed Point"]
            })

            with open("PB2002_boundaries.json", "r") as f:
                plates_geojson = json.load(f)

            with open("Exclusive Economic Zone (Perth Treaty) limits.geojson", "r") as f:
                eez_geojson = json.load(f)
            
            with open("Continental Shelf limits.geojson", "r") as f:
                shelf_geojson = json.load(f)

            for feat in plates_geojson.get("features", []):
                feat.setdefault("properties", {})["label"] = "Tectonic Plates Boundary"

            for feat in eez_geojson.get("features", []):
                feat.setdefault("properties", {})["label"] = "Exclusive Economic Zone"

            for feat in shelf_geojson.get("features", []):
                feat.setdefault("properties", {})["label"] = "Continental Shelf"

            plate_layer = pdk.Layer(
                "GeoJsonLayer",
                data=plates_geojson,
                stroked=True,
                filled=False,
                get_line_color=[255, 140, 0],   # orange
                get_line_width=80,              # width in "meters-ish" depending on zoom; tweak as needed
                line_width_min_pixels=2,
                pickable=True,
                wrap_longitude=True
            )

            eez_layer = pdk.Layer(
                "GeoJsonLayer",
                data=eez_geojson,
                stroked=True,
                filled=False,
                get_line_color=[52, 207, 235],  
                get_line_width=80,              # width in "meters-ish" depending on zoom; tweak as needed
                line_width_min_pixels=2,
                pickable=True,
                wrap_longitude=True
            )

            shelf_layer = pdk.Layer(
                "GeoJsonLayer",
                data=shelf_geojson,
                stroked=True,
                filled=False,
                get_line_color=[0, 255, 0],   # green
                get_line_width=80,              # width in "meters-ish" depending on zoom; tweak as needed
                line_width_min_pixels=2,
                pickable=True,
                wrap_longitude=True
            )

            point_layer = pdk.Layer(
                "ScatterplotLayer",
                data=df,
                get_position=["lon", "lat"],
                get_radius=50000,
                get_fill_color=[255, 0, 0],
                pickable=True
            )

            
            view_state = pdk.ViewState(
                latitude=df.loc[0, "lat"],
                longitude=df.loc[0, "lon"],
                zoom=3,
            )

            st.pydeck_chart(
                pdk.Deck(
                    layers=[plate_layer, point_layer, eez_layer, shelf_layer],
                    tooltip={"text": "{label}"},
                    initial_view_state=view_state,
                    map_style="light"
                )
            )

            st.markdown("### Legend")
            st.markdown("🔴 **Site**")
            st.markdown("🟠 **Plate boundaries**")
            st.markdown("🔵 **Exclusive Economic Zone**")
            st.markdown("🟢 **Continental Shelf**")

