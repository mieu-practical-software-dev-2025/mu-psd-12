import os
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI # Import the OpenAI library
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# Flaskアプリケーションのインスタンスを作成
# static_folderのデフォルトは 'static' なので、
# このファイルと同じ階層に 'static' フォルダがあれば自動的にそこが使われます。
app = Flask(__name__)

# 開発モード時に静的ファイルのキャッシュを無効にする
if app.debug:
    @app.after_request
    def add_header(response):
        # /static/ 以下のファイルに対するリクエストの場合
        if request.endpoint == 'static':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache' # HTTP/1.0 backward compatibility
            response.headers['Expires'] = '0' # Proxies
        return response


# OpenRouter APIキーと関連情報を環境変数から取得
# このキーはサーバーサイドで安全に管理してください
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("YOUR_SITE_URL", "http://localhost:5000") # Default if not set
APP_NAME = os.getenv("YOUR_APP_NAME", "FlaskVueApp") # Default if not set

# URL:/ に対して、static/index.htmlを表示して
    # クライアントサイドのVue.jsアプリケーションをホストする
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')
    
# URL:/send_api に対するメソッドを定義
@app.route('/send_api', methods=['POST'])
def send_api():
    if not OPENROUTER_API_KEY:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={ # Recommended by OpenRouter
            "HTTP-Referer": SITE_URL,
            "X-Title": APP_NAME,
        }
    )
    
    # POSTリクエストからJSONデータを取得
    data = request.get_json()

    # 'text'フィールドがリクエストのJSONボディに存在するか確認
    if not data or 'text' not in data:
        app.logger.error("Request JSON is missing or does not contain 'text' field.")
        return jsonify({"error": "Missing 'text' in request body"}), 400

    received_text = data['text']
    if not received_text.strip(): # 空文字列や空白のみの文字列でないか確認
        app.logger.error("Received text is empty or whitespace.")
        return jsonify({"error": "Input text cannot be empty"}), 400
    
    # systemプロンプトの設定
    system_prompt = "あなたは「相手と親しくしたい」という下心を持ったおじさんです。ユーザーからの入力を、次の条件を満たすようなおじさん構文に変換してください : "
    prompt_cond = ["絵文字を多用する", "カタカナを多用する", "読点を多用する", "敬語が「だヨ～」「ネ～」になる", "疑問文末が「カナ❓」である", "気遣いや誘いをする", "140字以内である"]
    system_prompt += "、".join(prompt_cond)
    app.logger.info(f"Using system prompt: {system_prompt}")

    try:
        # OpenRouter APIを呼び出し
        # モデル名はOpenRouterで利用可能なモデルを指定してください。
        # 例: "mistralai/mistral-7b-instruct", "google/gemini-pro", "openai/gpt-3.5-turbo"
        # 詳細はOpenRouterのドキュメントを参照してください。
        chat_completion = client.chat.completions.create(
            messages=[ # type: ignore
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": received_text}
            ], # type: ignore
            model="google/gemma-3-27b-it:free", 
        )
        
        # APIからのレスポンスを取得
        if chat_completion.choices and chat_completion.choices[0].message:
            processed_text = chat_completion.choices[0].message.content
        else:
            processed_text = "AIから有効な応答がありませんでした。"
            
        return jsonify({"message": "AIによってデータが処理されました。", "processed_text": processed_text})

    except Exception as e:
        app.logger.error(f"OpenRouter API call failed: {e}")
        # クライアントには具体的なエラー詳細を返しすぎないように注意
        return jsonify({"error": f"AIサービスとの通信中にエラーが発生しました。"}), 500

# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    if not OPENROUTER_API_KEY:
        print("警告: 環境変数 OPENROUTER_API_KEY が設定されていません。API呼び出しは失敗します。")
    app.run(debug=True, host='0.0.0.0', port=5000)