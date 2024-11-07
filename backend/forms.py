# Import necessary modules
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length


# Define registration form class
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
                           DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[
                             DataRequired(), Length(min=8, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[
                        DataRequired(), Length(min=10, max=15)])
    dob = StringField('Date of Birth', validators=[DataRequired()])
    gender = StringField('Gender', validators=[DataRequired()])
    submit = SubmitField('Register')


# Define login form class
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')
