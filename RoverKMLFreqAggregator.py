import streamlit as st
import xml.etree.ElementTree as ET
import re
import csv
import os
import io

ET.register_namespace('', "http://www.opengis.net/kml/2.2")

def round_frequency(freq_str, decimal_places):
    try:
        freq = float(freq_str)
        rounded_freq = round(freq * (10 ** decimal_places)) / (10 ** decimal_places)
        return f"{rounded_freq:.{decimal_places}f}"
    except ValueError:
        return freq_str

def update_name(element, old_freq, new_freq):
    name = element.find('{http://www.opengis.net/kml/2.2}name')
    if name is not None and old_freq in name.text:
        name.text = name.text.replace(old_freq, new_freq)

def update_all_names(element, old_freq, new_freq):
    update_name(element, old_freq, new_freq)
    for child in element:
        update_name(child, old_freq, new_freq)

def read_csv_frequencies(csv_file, decimal_places):
    frequencies = set()
    csv_reader = csv.reader(io.StringIO(csv_file.getvalue().decode("utf-8")))
    next(csv_reader)  # Skip header
    for row in csv_reader:
        if row:
            rounded_freq = round_frequency(row[0], decimal_places)
            frequencies.add(rounded_freq)
    return frequencies

def parse_kml(kml_file, csv_file, decimal_places):
    tree = ET.parse(io.BytesIO(kml_file.getvalue()))
    root = tree.getroot()

    st.write(f"Root tag: {root.tag}")
    for child in root:
        st.write(f"Child tag: {child.tag}")

    folders = root.findall('.//{http://www.opengis.net/kml/2.2}Folder')
    st.write(f"Number of folders found: {len(folders)}")

    document = root.find('{http://www.opengis.net/kml/2.2}Document')

    folder_dict = {}

    for folder in folders:
        name = folder.find('{http://www.opengis.net/kml/2.2}name')
        if name is not None and "MHz" in name.text:
            original_freq = re.search(r'(\d+\.\d+)', name.text).group(1)
            rounded_freq = round_frequency(original_freq, decimal_places)

            if rounded_freq not in folder_dict:
                folder_dict[rounded_freq] = folder
                update_all_names(folder, original_freq, rounded_freq)
                st.write(f"Created folder for: {rounded_freq} MHz")
            else:
                target_folder = folder_dict[rounded_freq]

                lobs_folder = folder.find('{http://www.opengis.net/kml/2.2}Folder[{http://www.opengis.net/kml/2.2}name="LOBs"]')
                if lobs_folder is not None:
                    target_lobs_folder = target_folder.find('{http://www.opengis.net/kml/2.2}Folder[{http://www.opengis.net/kml/2.2}name="LOBs"]')
                    if target_lobs_folder is None:
                        target_lobs_folder = ET.SubElement(target_folder, '{http://www.opengis.net/kml/2.2}Folder')
                        ET.SubElement(target_lobs_folder, '{http://www.opengis.net/kml/2.2}name').text = "LOBs"
                    for lob in lobs_folder:
                        update_all_names(lob, original_freq, rounded_freq)
                        target_lobs_folder.append(lob)
                        st.write(f"Moving LOBs from {original_freq} to {rounded_freq} MHz")

                folder.clear()
                folder.tag = 'ToRemove'

    # First pass removal
    for elem in document.findall('.//*[@tag="ToRemove"]'):
        parent = elem.find('..')
        if parent is not None:
            parent.remove(elem)

    # Second pass: Remove folders based on CSV (if provided)
    if csv_file is not None:
        csv_frequencies = read_csv_frequencies(csv_file, decimal_places)
        for freq, folder in folder_dict.items():
            if freq in csv_frequencies:
                folder.clear()
                folder.tag = 'ToRemove'
                st.write(f"Marked for removal (CSV match): {freq} MHz")

        # Second pass removal
        for elem in document.findall('.//*[@tag="ToRemove"]'):
            parent = elem.find('..')
            if parent is not None:
                parent.remove(elem)
    else:
        st.write("No CSV file provided. Skipping second pass filtering.")

    st.write(f"Grouped into {len(folder_dict)} unique frequencies")

    # Convert the processed XML tree to a string
    output = io.BytesIO()
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()

def main():
    st.title("Rover KML Frequency Aggregator")

    kml_file = st.file_uploader("Upload KML file", type=['kml'])
    csv_file = st.file_uploader("Upload CSV file (optional)", type=['csv'])
    decimal_places = st.number_input("Number of decimal places to round to", min_value=0, max_value=10, value=1)

    if st.button("Process KML"):
        if kml_file is not None:
            processed_kml = parse_kml(kml_file, csv_file, decimal_places)
            
            st.download_button(
                label="Download processed KML",
                data=processed_kml,
                file_name="processed_kml.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
        else:
            st.error("Please upload a KML file.")

if __name__ == "__main__":
    main()
