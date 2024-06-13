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

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run django migrations
RUN python manage.py makemigrations
RUN python manage.py migrate

# Create superuser
RUN echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'admin')" | python manage.py shell

# Create AppSettings
RUN echo "from dashboard.models import AppSettings; from django.contrib.auth.models import User; AppSettings.objects.create(user=User.objects.get(username='admin'))" | python manage.py shell

# Run server when the container launches
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
