# Test Results Images

This directory contains screenshots of test results for the LineGPT application.

## Adding Your Own Test Results

1. Take a screenshot of your test results from any of the debugging endpoints:
   - `/test_message`
   - `/test_chinese`
   - `/test_broadcast`
   - `/test_encoding`
   - `/raw_message`

2. Save the screenshot to this directory with a descriptive name, for example:
   - `test_results.png` (main test results shown in the main README)
   - `chinese_test_results.png` (results of testing Chinese message sending)
   - `broadcast_test_results.png` (results of testing broadcast functionality)

3. Update the main README.md file to reference your new images if needed:
   ```markdown
   ![Chinese Test Results](images/chinese_test_results.png)
   ```

## Example Screenshot

Here's what your test results might look like:

```
{
  "success": true,
  "results": [
    {
      "message": "你好，这是一条测试消息。",
      "success": true,
      "status_code": 200,
      "response": {
        "message": "ok"
      }
    },
    {
      "message": "Hello, this is a test message.",
      "success": true,
      "status_code": 200,
      "response": {
        "message": "ok"
      }
    }
    // ... more results ...
  ]
}
```

## Troubleshooting

If your tests are failing, check the following:
1. Your LINE Channel Access Token is valid
2. The user ID you're using exists and is correct
3. Your application is properly logging the request and response
4. The LINE API is returning success responses

You can use the logs from your application to diagnose issues with message sending. 