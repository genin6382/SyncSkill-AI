Activity:

1. Create React Vite App
2. Create flask app for api
3. Create models.py
4. Connect flask to mysql database
5. Create basic endpoints /login , /register .
6. Deny access without login 
7. Create a sample Home page to upload user document and send it flask
8. Create a S3 bucket and lambda function to store the document to s3 bucket
9. Add restriction in frontend/backend - Document size < 1MB 
10. Flask receives request and sends to lambda function url.

==After document is uploaded==

11. Create An EventBridge Event to trigger -> Lambda -> Extracts text using AWS Textract -> store in S3
12. If success , call a lambda function -> to get_text_from_s3 . Add a sleep(5) in backend bfr calling this .
13. Store the extracted_text in table for given user.

14. Get the dataset that contains - Job portals , company names , salary , skills , description , role , etc for each Job
15. Reduced the size of dataset from (1610462rows, 12cols, 1.78GB) to (376rows, 42cols ,1.2MB).
16. Setup chromaDB as vector database and hugging face for embedding.
17. Input query from user. Use Query + Resume_text to search the Job dataset in vector db
18. Give the final response by providing this as context to LLM .

/health api for k8s