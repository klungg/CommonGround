1. __List all projects__:

   ```bash
   curl -X GET http:///127.0.0.1:8000/projects
   ```

2. __Get details of a specific project__: Replace `<project_id>` with the actual project ID.

   ```bash
   curl -X GET http:///127.0.0.1:8000/project/<project_id>
   ```

3. __Create a new project__: Replace `<project_name>` with the desired project name.

   ```bash
   curl -X POST "http:///127.0.0.1:8000/project" -d '{"name": "test_project"}'
   ```

4. __Update the name of a project__: Replace `<project_id>` with the actual project ID and `<new_project_name>` with the new name.

   ```bash
   curl -X PUT http:///127.0.0.1:8000/project/1546582f-e1f9-4cbd-905e-795ff516d3de \
   -H "Content-Type: application/json" \
   -d '{"name": "test_project_updated"}'
   ```

5. __Delete a project (soft delete)__: Replace `<project_name>` with the name of the project to delete.

   ```bash
   curl -X DELETE "http:///127.0.0.1:8000/project/1546582f-e1f9-4cbd-905e-795ff516d3de"
   ```

These commands assume the server is running locally on port 8000. Adjust the URL if the server is hosted elsewhere or on a different port.
