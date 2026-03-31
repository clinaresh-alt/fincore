"use client";

import { useEffect } from "react";
import { useChatConfig } from "@/features/support/hooks/use-support";

declare global {
  interface Window {
    $crisp?: unknown[];
    CRISP_WEBSITE_ID?: string;
    Intercom?: (action: string, ...args: unknown[]) => void;
    intercomSettings?: Record<string, unknown>;
  }
}

export function ChatWidget() {
  const { data: config, isLoading } = useChatConfig();

  useEffect(() => {
    if (isLoading || !config) return;

    if (config.provider === "crisp" && config.website_id) {
      // Load Crisp
      window.$crisp = [];
      window.CRISP_WEBSITE_ID = config.website_id;

      const script = document.createElement("script");
      script.src = "https://client.crisp.chat/l.js";
      script.async = true;
      document.head.appendChild(script);

      // Set user data once Crisp is loaded
      script.onload = () => {
        if (config.user_data && window.$crisp) {
          window.$crisp.push(["set", "user:email", [config.user_data.email]]);
          if (config.user_data.nickname) {
            window.$crisp.push([
              "set",
              "user:nickname",
              [config.user_data.nickname],
            ]);
          }
          if (config.user_data.user_id) {
            window.$crisp.push([
              "set",
              "session:data",
              [[["user_id", config.user_data.user_id]]],
            ]);
          }
        }
      };

      return () => {
        // Cleanup
        document.head.removeChild(script);
        delete window.$crisp;
        delete window.CRISP_WEBSITE_ID;
      };
    }

    if (config.provider === "intercom" && config.app_id) {
      // Load Intercom
      window.intercomSettings = {
        api_base: "https://api-iam.intercom.io",
        app_id: config.app_id,
        ...config.user_data,
        ...config.settings,
      };

      const script = document.createElement("script");
      script.innerHTML = `
        (function(){var w=window;var ic=w.Intercom;if(typeof ic==="function"){ic('reattach_activator');ic('update',w.intercomSettings);}else{var d=document;var i=function(){i.c(arguments);};i.q=[];i.c=function(args){i.q.push(args);};w.Intercom=i;var l=function(){var s=d.createElement('script');s.type='text/javascript';s.async=true;s.src='https://widget.intercom.io/widget/${config.app_id}';var x=d.getElementsByTagName('script')[0];x.parentNode.insertBefore(s,x);};if(document.readyState==='complete'){l();}else if(w.attachEvent){w.attachEvent('onload',l);}else{w.addEventListener('load',l,false);}}})();
      `;
      document.body.appendChild(script);

      return () => {
        // Cleanup
        if (window.Intercom) {
          window.Intercom("shutdown");
        }
        document.body.removeChild(script);
        delete window.Intercom;
        delete window.intercomSettings;
      };
    }
  }, [config, isLoading]);

  // This component doesn't render anything visible
  // The chat widget is injected by the third-party scripts
  return null;
}
