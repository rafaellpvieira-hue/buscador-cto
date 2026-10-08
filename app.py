            f"CTO: {cto_input}\n"
            f"PORTA: {porta_input}\n"
            f"ONU NOVA s/n: {onu_sn_input}"
        )
    else:
        texto_whatsapp_onu = (
            f"*ATIVAÇÃO DE ONU*\n"
            f"Protocolo: {protocolo_input}\n"
            f"PPPOE: {pppoe_input}\n"
            f"CTO: {cto_input}\n"
            f"PORTA: {porta_input}\n"
            f"ONU s/n: {onu_sn_input}\n"
            f"Cidade: {cidade_input}"
        )

    st.write("---")
    st.markdown("📋 **Texto gerado para o WhatsApp:**")
    st.code(texto_whatsapp_onu, language=None)

    texto_json = json.dumps(texto_whatsapp_onu)
    b64_json = json.dumps(b64_foto)
    mime_json = json.dumps(mime_type)
    nome_json = json.dumps(nome_foto)

    html_share = f"""
    <div style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; gap: 10px;">
        <button onclick="abrirDiretoWhatsapp()" style="
            background-color: #25D366;
            color: white;
            border: none;
            padding: 14px 20px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            max-width: 450px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        ">
            🟢 1. Abrir Direto no WhatsApp
        </button>

        <button onclick="compartilharNative()" style="
            background-color: #0088cc;
            color: white;
            border: none;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            max-width: 450px;
        ">
            📲 2. Compartilhar Imagem + Texto
        </button>

        <div id="shareStatus" style="font-size: 13px; color: #ffeb3b; text-align: center; max-width: 450px; font-weight: bold;"></div>
    </div>

    <script>
    const texto = {texto_json};
    const b64Data = {b64_json};
    const mimeType = {mime_json};
    const fileName = {nome_json};

    async function abrirDiretoWhatsapp() {{
        const statusDiv = document.getElementById("shareStatus");
        
        if (b64Data) {{
            try {{
                const byteCharacters = atob(b64Data);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {{
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }}
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {{ type: mimeType }});

                await navigator.clipboard.write([
                    new ClipboardItem({{ [mimeType]: blob }})
                ]);
                statusDiv.innerHTML = "✅ <b>Foto copiada!</b> Abrindo o WhatsApp... Toque na conversa e escolha <b>'Colar'</b> para anexar a foto.";
            }} catch (e) {{
                statusDiv.innerHTML = "ℹ️ Abrindo WhatsApp com o texto. Anexe a foto manualmente se necessário.";
            }}
        }} else {{
            statusDiv.innerHTML = "Abrindo WhatsApp...";
        }}

        setTimeout(() => {{
            const url = "https://api.whatsapp.com/send?text=" + encodeURIComponent(texto);
            window.open(url, "_blank");
        }}, 400);
    }}

    async function compartilharNative() {{
        const statusDiv = document.getElementById("shareStatus");
        if (b64Data && navigator.share) {{
            try {{
                const byteCharacters = atob(b64Data);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {{
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }}
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {{ type: mimeType }});
                const file = new File([blob], fileName, {{ type: mimeType }});

                if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                    await navigator.share({{
                        files: [file],
                        title: 'Envio ONU',
                        text: texto
                    }});
                    statusDiv.innerText = "✅ Compartilhado!";
                    return;
                }}
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    console.log("Erro:", err);
                }}
            }}
        }}
        
        const url = "https://api.whatsapp.com/send?text=" + encodeURIComponent(texto);
        window.open(url, "_blank");
    }}
    </script>
    """
    components.html(html_share, height=160)
