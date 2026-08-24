import httpx

def main():
    with httpx.Client(base_url="http://127.0.0.1:8000") as client:
        res = client.post("/api/websites", json={
            "domain": "accident.innovatcs.com",
            "cms_url": "https://accident.innovatcs.com",
            "cms_user": "admin",
            "app_password": "sample_app_password_123"
        })
        print("Create Website Status:", res.status_code)
        print("Create Website Body:", res.text)

        res_list = client.get("/api/websites")
        print("List Websites:", res_list.json())

if __name__ == "__main__":
    main()
