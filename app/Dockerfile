# Use an official Python runtime as a parent image
FROM python:3.11

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Install polish locale
RUN apt-get update && apt-get install -y locales
RUN sed -i '/pl_PL.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LC_ALL pl_PL.UTF-8
ENV LANG pl_PL.UTF-8
ENV LANGUAGE pl_PL.UTF-8

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Define the command to run your Streamlit app
CMD ["streamlit", "run", "dashboard.py"]
