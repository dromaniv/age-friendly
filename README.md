# age-friendly

We're currently in the process of developing a program that will effectively address the accessibility needs of people with limited mobility. This program will work by utilizing advanced mapping and data analysis techniques to classify streets based on the availability of benches.

## Setup

### Easy way:

1. Install [Docker](https://www.docker.com/get-started)

2. Run `docker build -t age-friendly app` in the root directory of the project

3. Run `docker run -p 8501:8501 --rm age-friendly` in the root directory of the project

4. Go to [`localhost:8501`](http://localhost:8501) in your browser

### Hard way:

1. Install [Python 3.11.0](https://www.python.org/downloads/release/python-3110/)

2. Install [pip](https://pip.pypa.io/en/stable/installation/)

3. Install [Git](https://git-scm.com/downloads)

4. Clone the repository by running `git clone age-friendly` in the directory you want to clone the repository to

5. Run `pip install -r app/requirements.txt` in the root directory of the project

6. Run `streamlit run app/app.py` in the root directory of the project

7. Go to [`localhost:8501`](http://localhost:8501) in your browser
