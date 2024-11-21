import streamlit as st

# Set page configuration (optional)
st.set_page_config(page_title="About Age Friendly", page_icon="ℹ️")

# About Page Content
st.title("Age Friendly")

st.markdown(
    """
    **This application is the result of collaboration between two Faculties - Computing Sciences and Architecture of Poznan University of Technology, Poznan, Poland.**

    ### **Team:**

    **Faculty of Computing Sciences (CS):**
    - Dmytro Romaniv
    - Patryk Maciejewski
    - Michał Skrzypek
    - Eryk Walter
    - Rafael Fialho
    - Prof. Dariusz Brzeziński, D.Sc.Eng.
    - Prof. Jerzy Stefanowski, D.Sc.Eng.

    **Faculty of Architecture (FA):**
    - Agnieszka Ptak-Wojciechowska, Ph.D.Eng.Arch
    - Prof. Agata Gawlak, D.Sc.Eng.Arch.

    ### **Application Overview:**

    The app shows the current location of the benches in an area of the selected scale, from the neighbourhood to the districts to the administrative borders of the city. Based on pre-set parameters for the distance between benches, it allows individual streets to be assessed in terms of their friendliness to older people. An additional feature is the generation of improvement scenarios assuming a specific budget and bench price.

    In the application, there is also an option for a heatmap covering demographic statistics regarding the population of retired people (if available for the given city).

    ### **Contact:**
    For any queries or contributions, please reach out to the team members listed above or contact the respective faculties at Poznan University of Technology.
    """
)

# You can also add links to team members' profiles or university pages
st.markdown(
    """
    ### **University:**
    [Poznan University of Technology](https://put.poznan.pl/)

    ### **Faculties:**
    - [Faculty of Computing Sciences](https://cat.put.poznan.pl/)
    - [Faculty of Architecture](https://architektura.put.poznan.pl/)
    """
)
