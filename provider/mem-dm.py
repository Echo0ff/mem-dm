from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
import httpx


class MemDmProvider(ToolProvider):
    
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            base_url = credentials.get("base_url", "").rstrip("/")
            if not base_url:
                raise ValueError("base_url is required")

            # 简单健康检查：尝试访问根路径或 /docs
            ok = False
            for path in ["/", "/docs"]:
                try:
                    r = httpx.get(f"{base_url}{path}", timeout=5, follow_redirects=False)
                    if r.status_code in (200, 307):
                        ok = True
                        break
                except Exception:
                    continue
            if not ok:
                # 再尝试一次 /memories?user_id=dify_ping (DELETE 不执行，只校验可连通 POST /search)
                try:
                    r = httpx.post(f"{base_url}/search", json={"query": "ping", "user_id": "dify_ping"}, timeout=5)
                    ok = r.status_code in (200, 400, 422)
                except Exception:
                    ok = False
            if not ok:
                raise ValueError("Cannot reach mem-dm service with provided base_url")
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))

    #########################################################################################
    # If OAuth is supported, uncomment the following functions.
    # Warning: please make sure that the sdk version is 0.4.2 or higher.
    #########################################################################################
    # def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
    #     """
    #     Generate the authorization URL for mem-dm OAuth.
    #     """
    #     try:
    #         """
    #         IMPLEMENT YOUR AUTHORIZATION URL GENERATION HERE
    #         """
    #     except Exception as e:
    #         raise ToolProviderOAuthError(str(e))
    #     return ""
        
    # def _oauth_get_credentials(
    #     self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    # ) -> Mapping[str, Any]:
    #     """
    #     Exchange code for access_token.
    #     """
    #     try:
    #         """
    #         IMPLEMENT YOUR CREDENTIALS EXCHANGE HERE
    #         """
    #     except Exception as e:
    #         raise ToolProviderOAuthError(str(e))
    #     return dict()

    # def _oauth_refresh_credentials(
    #     self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    # ) -> OAuthCredentials:
    #     """
    #     Refresh the credentials
    #     """
    #     return OAuthCredentials(credentials=credentials, expires_at=-1)
