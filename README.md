# Age-Friendly

We are developing a program to effectively address the accessibility needs of people with limited mobility. This program uses advanced mapping and data analysis techniques to classify streets based on the availability of benches, helping create more age-friendly environments.

## Setup

### Prerequisites
- Install [Git](https://git-scm.com/downloads) and clone the repository by running:

  ```bash
  git clone https://github.com/Dmytro-Romaniv/age-friendly.git
  ```
  in the directory where you want to clone the repository.

### Option 1: Streamlit Version

#### With Docker (Recommended)

1. Install [Docker](https://www.docker.com/get-started).
2. In the `streamlit` directory of the project, run:
   
   ```bash
   docker build -t age-friendly-streamlit .
   ```

3. Then run the container:
   
   ```bash
   docker run -p 8501:8501 --rm -v $(pwd):/streamlit age-friendly-streamlit
   ```

#### Without Docker

1. Install [Python 3.11.0](https://www.python.org/downloads/release/python-3110/).
2. Install [pip](https://pip.pypa.io/en/stable/installation/).
   
   In the `streamlit` directory of the project:

3. Install the project dependencies:
   
   ```bash
   pip install -r requirements.txt
   ```

4. Run the Streamlit app:

   ```bash
   streamlit run app.py
   ```

### Option 2: Django Version

#### With Docker (Recommended)

1. Install [Docker](https://www.docker.com/get-started).
2. In the `django` directory of the project, run:
   
   ```bash
   docker build -t age-friendly-django .
   ```

3. Then run the container:
   
   ```bash
   docker run -p 8000:8000 --rm age-friendly-django
   ```

#### Without Docker

1. Install [Python 3.11.0](https://www.python.org/downloads/release/python-3110/).
2. Install [pip](https://pip.pypa.io/en/stable/installation/).
   
   In the `django` directory of the project:

3. Install the project dependencies:
   
   ```bash
   pip install -r requirements.txt
   ```

4. Run database migrations:

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. Create a superuser:

   ```bash
   python manage.py createsuperuser
   ```

6. Start the Django development server:

   ```bash
   python manage.py runserver
   ```

## Usage

1. Open your browser and navigate to the [Streamlit UI](http://localhost:8501/) or the [Django UI](http://localhost:8000/).
    > Use the login credentials `admin` for both username and password.
2. Enter the city name in the designated field.
3. You can either fill out the street field or leave it empty to display all streets.
4. _(Optional)_ Adjust the street length slider if the entire street is not highlighted.
5. Click the "Show" button to view the results.

## Useful Tools

- [OpenStreetMap Search Engine](https://nominatim.openstreetmap.org/ui/search.html?q=Grobla%2C+Pozna%C5%84)
- [OSMnx Documentation](https://osmnx.readthedocs.io/en/stable/)