// ... existing code ...
            if response.status_code != 200:
                error_msg = f"Langflow API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    
                    # Check for context length exceeded error
                    if isinstance(error_detail, dict) and 'detail' in error_detail:
                        detail_str = str(error_detail['detail'])
                        if 'maximum context length' in detail_str and 'tokens' in detail_str:
                            logger.error(f"Context length exceeded: {detail_str}")
                            raise HTTPException(
                                status_code=413,  # Payload Too Large
                                detail=(
                                    "The query generated too much data for the AI model to process. "
                                    "Please try to make your query more specific or break it into smaller parts."
                                )
                            )
                    
                    error_msg += f": {json.dumps(error_detail)}"
                except:
                    error_msg += f": {response.text}"
                
                logger.error(error_msg)
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_msg
                )
// ... existing code ...