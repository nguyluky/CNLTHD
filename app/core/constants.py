# # Email: text/number/special + @ + domain + .extension
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# # Phone: 10 digits long and starts with 0
PHONE_REGEX = r"^0[3|5|7|8|9][0-9]{8}$"