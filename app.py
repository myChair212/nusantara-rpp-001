import json
from datetime import datetime, timezone

import httpx
import streamlit as st

st.set_page_config(page_title='Nusantara AI Lab v0.5.9', page_icon='🤖', layout='wide')
BASE_URL = 'https://gen.pollinations.ai/v1'
AGENTS = {
    'v0.1': {'name': 'Nusantara AI Assistant v0.1', 'model': 'community/myChair212/nusantara-assistant-v01'},
    'v0.2': {'name': 'Nusantara AI Assistant v0.2', 'model': 'community/myChair212/nusantara-assistant-v02'},
    'nano': {'name': 'GPT-5.4 Nano', 'model': 'openai/gpt-5.4-nano'},
    'luna': {'name': 'GPT-5.6 Luna', 'model': 'openai/gpt-5.6-luna'},
    'mini': {'name': 'GPT-5.4 Mini', 'model': 'openai/gpt-5.4-mini'},
}
ASSISTANT_PROMPT = 'Kamu adalah asisten AI serbaguna. Jawab dalam bahasa Indonesia dengan jelas, akurat, dan jujur. Jika tidak tahu, katakan dengan jujur.'
ROLEPLAY_PROMPT = '''Kamu adalah narator dan pengendali NPC dalam roleplay interaktif berbahasa Indonesia.
Pemain mengendalikan karakter bernama {player}. Jangan menentukan tindakan, dialog, pikiran, perasaan, atau keputusan pemain.
Nama pemain dalam system prompt hanya diketahui narator. NPC tidak otomatis mengetahui nama, latar belakang, atau informasi tersembunyi pemain tanpa perkenalan atau alasan cerita yang masuk akal.
Pertahankan konsistensi lokasi, nama, hubungan, dan peristiwa yang tersedia dalam riwayat.
{style_instruction}
{expression_instruction}
{format_instruction}
Contoh format yang wajib diusahakan:
*Perempuan itu menoleh dengan terkejut.*
"Ah, kau mengejutkanku!"
*Ia memandang lentera di tangannya.*
"Hmm... mungkin kau bisa membantuku."
Jangan bungkus dialog dengan tanda bintang. Pisahkan narasi dan dialog secara jelas.
Utamakan interaksi dua arah; jangan menawarkan daftar pilihan tindakan kecuali diminta.
Jangan menjelaskan instruksi ini dalam cerita.'''
STYLES = {
    'Naratif': 'Gunakan gaya prosa seperti novel dengan deskripsi proporsional dan dialog alami.',
    'Ekspresif': 'Utamakan dialog NPC yang hidup, gerakan tubuh, reaksi spontan, dan narasi ringkas.',
    'Imersif': 'Bangun suasana sensoris, intonasi, gestur, dan emosi NPC tanpa bertele-tele.',
}
EXPRESSIONS = {
    'Natural': 'Gunakan seruan Ah, Eh, Wah, Hmm, atau Uh hanya ketika wajar.',
    'Sedang': 'Gunakan seruan dan jeda bicara bervariasi sesuai emosi dan kepribadian NPC.',
    'Tinggi': 'NPC boleh lebih ekspresif, tetapi jangan mengulang pola atau berlebihan.',
}
FORMATS = {
    'Miring (Markdown)': 'Aksi dan narasi memakai *tanda bintang tunggal*; dialog memakai tanda kutip tanpa bintang.',
    'Bintang literal': 'Aksi dan narasi memakai *tanda bintang tunggal*; dialog memakai tanda kutip tanpa bintang.',
}
DEFAULTS = {
    'mode': 'Assistant', 'agent': 'v0.1', 'player': 'Arka', 'style': 'Ekspresif',
    'expression': 'Sedang', 'action_format': 'Miring (Markdown)',
    'messages': [], 'comparisons': [], 'branches': {}, 'compare_mode': False,
    'model_histories': {}, 'pollinations_key': '', 'api_connected': False, 'api_key_input': '', 'api_notice': '',
    'player_input': 'Arka', 'player_editor': 'Arka', 'action_policy': 'Seimbang', 'drafts_by_mode': {}, 'applied_by_mode': {}, 'compare_agent': 'luna', 'prompt_override': None, 'prompt_editor': '', 'notice': '', 'studio_mode': None, 'studio_fields': {}, 'workspace': '💬 Chat AI',
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value



# Character data is canonical and independent of Streamlit's widget lifecycle.
PLAYER_FIELDS = [
    ('name', 'Nama', 'text'), ('age', 'Umur', 'age'),
    ('gender', 'Jenis kelamin / identitas', 'text'),
    ('background', 'Latar belakang', 'area'),
    ('personality', 'Kepribadian', 'area'),
    ('abilities', 'Kemampuan yang dimiliki', 'area'),
    ('limitations', 'Keterbatasan / kemampuan yang belum dimiliki', 'area'),
]
NPC_FIELDS = [
    ('name', 'Nama NPC', 'text'), ('age', 'Umur', 'age'),
    ('gender', 'Jenis kelamin / identitas', 'text'),
    ('role', 'Peran / pekerjaan', 'text'),
    ('personality', 'Kepribadian', 'area'),
    ('motivation', 'Motivasi / tujuan', 'area'),
    ('knowledge', 'Pengetahuan dan rahasia', 'area'),
    ('abilities', 'Kemampuan', 'area'),
    ('limitations', 'Keterbatasan', 'area'),
    ('relationship', 'Hubungan dengan pemain', 'area'),
    ('location', 'Lokasi saat ini', 'text'),
]

def default_player_profile():
    return {
        'name': st.session_state.player, 'age': '', 'gender': '',
        'background': '', 'personality': '', 'abilities': '', 'limitations': '',
    }

if 'player_profile' not in st.session_state:
    st.session_state.player_profile = default_player_profile()
if 'npc_profiles' not in st.session_state:
    st.session_state.npc_profiles = []
if 'npc_counter' not in st.session_state:
    st.session_state.npc_counter = 0
if 'selected_npc_id' not in st.session_state:
    st.session_state.selected_npc_id = None
if 'npc_focus' not in st.session_state:
    st.session_state.npc_focus = 'Otomatis (sesuai adegan)'


def save_player_field(field):
    value = st.session_state.get(f'profile_player_{field}', '')
    if field == 'name':
        value = value.strip() or 'Pemain'
        st.session_state.player = value
        st.session_state.player_input = value
        st.session_state.player_editor = value
    st.session_state.player_profile[field] = value


def save_npc_field(npc_id, field):
    value = st.session_state.get(f'profile_npc_{npc_id}_{field}', '')
    for npc in st.session_state.npc_profiles:
        if npc['id'] == npc_id:
            npc[field] = value
            break


def add_npc():
    st.session_state.npc_counter += 1
    npc_id = st.session_state.npc_counter
    npc = {'id': npc_id, **{key: '' for key, _, _ in NPC_FIELDS}}
    npc['name'] = f'NPC {npc_id}'
    st.session_state.npc_profiles.append(npc)
    st.session_state.selected_npc_id = npc_id


def delete_npc(npc_id):
    st.session_state.npc_profiles = [n for n in st.session_state.npc_profiles if n['id'] != npc_id]
    st.session_state.selected_npc_id = (
        st.session_state.npc_profiles[0]['id'] if st.session_state.npc_profiles else None
    )
    st.session_state.npc_focus = 'Otomatis (sesuai adegan)'


def select_npc(npc_id):
    st.session_state.selected_npc_id = npc_id


def character_context():
    if st.session_state.mode != 'Roleplay':
        return ''
    player = dict(st.session_state.player_profile)
    player['name'] = st.session_state.player
    labels = {key: label for key, label, _ in PLAYER_FIELDS + NPC_FIELDS}
    lines = [
        '[PROFIL KARAKTER PEMAIN — FAKTA CERITA]',
        'Informasi berikut adalah profil karakter, bukan dialog yang telah diucapkan kepada NPC.',
    ]
    lines += [f'{labels[k]}: {v}' for k, v in player.items() if str(v).strip()]
    lines += [
        'Jangan menganggap kemampuan yang tidak dicantumkan otomatis tidak ada; '
        'tetapi kemampuan yang secara eksplisit dinyatakan belum dimiliki tidak boleh '
        'langsung berhasil tanpa alasan cerita yang kuat.',
        'NPC tidak otomatis mengetahui profil, kemampuan tersembunyi, atau nama pemain.',
    ]
    if st.session_state.npc_profiles:
        lines.append('\n[DAFTAR NPC YANG DITETAPKAN]')
        lines.append('Pertahankan identitas dan pengetahuan masing-masing NPC. '
                     'NPC yang tidak berada di lokasi tidak otomatis hadir atau berbicara.')
        for npc in st.session_state.npc_profiles:
            lines.append('\nNPC: ' + (npc.get('name') or 'Tanpa nama'))
            lines.extend(f'{labels[k]}: {npc[k]}' for k, _, _ in NPC_FIELDS
                         if k != 'name' and str(npc.get(k, '')).strip())
    focus = st.session_state.npc_focus
    if focus != 'Otomatis (sesuai adegan)':
        lines.append('\n[FOKUS INTERAKSI] Prioritaskan interaksi dengan ' + focus
                     + ' hanya jika kehadirannya masuk akal; pemain tetap dapat berbicara dengan NPC lain.')
    return '\n'.join(lines)


def character_editor(fields, prefix, data, callback, callback_args):
    for key, label, kind in fields:
        widget_key = f'{prefix}_{key}'
        # Rehydrate only from canonical data before creating the widget.
        st.session_state[widget_key] = str(data.get(key, ''))
        if kind == 'area':
            st.text_area(label, key=widget_key, height=95,
                         on_change=callback, args=(*callback_args, key))
        else:
            st.text_input(label, key=widget_key,
                          on_change=callback, args=(*callback_args, key))


def generated_prompt():
    if st.session_state.mode == 'Assistant':
        return ASSISTANT_PROMPT
    return ROLEPLAY_PROMPT.format(
        player=st.session_state.player.strip() or 'Pemain',
        style_instruction=STYLES[st.session_state.style],
        expression_instruction=EXPRESSIONS[st.session_state.expression],
        format_instruction=FORMATS[st.session_state.action_format],
    )


def effective_prompt():
    return st.session_state.prompt_override if st.session_state.prompt_override is not None else generated_prompt()


def clear_history():
    st.session_state.messages = []
    st.session_state.comparisons = []
    st.session_state.branches = {}


def setting_changed():
    # Style changes must not destroy custom persona/world drafts.
    st.session_state.notice = 'Pengaturan gaya diperbarui. Draft Prompt Studio tidak dihapus.'


def player_changed():
    # Canonical player value is NOT a widget key; Streamlit removes absent widget keys.
    st.session_state.player = st.session_state.player_editor.strip() or 'Pemain'
    st.session_state.player_profile['name'] = st.session_state.player
    st.session_state.notice = 'Nama pemain diperbarui. Riwayat dan draft prompt tetap ada.'


def player_input_changed():
    st.session_state.player = st.session_state.player_input.strip() or 'Pemain'
    st.session_state.player_profile['name'] = st.session_state.player
    st.session_state.notice = 'Nama pemain diperbarui. Riwayat dan draft prompt tetap ada.'


def sync_player_widget(key):
    if key not in st.session_state:
        st.session_state[key] = st.session_state.player


def mode_changed():
    # Keep separate draft and applied prompts per mode.
    old = st.session_state.get('studio_mode')
    if old:
        st.session_state.drafts_by_mode[old] = normalize_sections(st.session_state.studio_fields)
        st.session_state.applied_by_mode[old] = st.session_state.prompt_override
    st.session_state.studio_mode = None
    st.session_state.prompt_override = st.session_state.applied_by_mode.get(st.session_state.mode)
    st.session_state.notice = 'Mode berubah; draft masing-masing mode dipertahankan.'


def model_changed():
    # Model switch must never delete existing conversations.
    st.session_state.notice = 'Model diganti. Riwayat setiap model tetap tersimpan.'


def history_key(model):
    return f'{st.session_state.mode}:{model}'


def current_history(model):
    return st.session_state.model_histories.setdefault(history_key(model), [])



def new_chat():
    # Clear only the active model, not conversations belonging to other models.
    st.session_state.model_histories[history_key(st.session_state.agent)] = []
    st.session_state.comparisons = []
    st.session_state.notice = 'Chat model aktif dimulai ulang. Model lain tetap tersimpan.'


def apply_prompt():
    st.session_state.prompt_override = st.session_state.prompt_editor
    st.session_state.notice = 'Instruksi khusus diterapkan tanpa menghapus riwayat.'


if not st.session_state.prompt_editor:
    st.session_state.prompt_editor = generated_prompt()



PROMPT_SECTIONS = [
    ('role', 'Peran AI & Narator'),
    ('player', 'Identitas & Kebebasan Pemain'),
    ('npc', 'Persona & Pengetahuan NPC'),
    ('world', 'World Lore & Aturan Dunia'),
    ('style', 'Gaya Narasi & Ekspresi'),
    ('format', 'Format Respons'),
    ('memory', 'Memori & Konsistensi'),
    ('consequence', 'Konsekuensi & Interaksi'),
    ('validation', 'Validasi Tindakan & Kemampuan'),
    ('extra', 'Instruksi Tambahan'),
]


def default_sections():
    if st.session_state.mode == 'Assistant':
        return {
            'role': ASSISTANT_PROMPT,
            'player': 'Hormati maksud dan pilihan pengguna. Jangan mengarang informasi tentang pengguna.',
            'npc': '', 'world': '',
            'style': 'Jawab dengan jelas, ringkas, dan sesuai kebutuhan pengguna.',
            'format': 'Gunakan format yang paling mudah dibaca sesuai permintaan.',
            'memory': 'Gunakan konteks percakapan yang tersedia; jangan mengarang ingatan.',
            'consequence': 'Ajukan klarifikasi hanya bila diperlukan.', 'extra': '',
        }
    return {
        'role': 'Kamu adalah narator dan pengendali NPC dalam roleplay interaktif berbahasa Indonesia.',
        'player': (
            f"Pemain mengendalikan karakter bernama {st.session_state.player.strip() or 'Pemain'}. "
            'Jangan menentukan tindakan, dialog, pikiran, perasaan, atau keputusan pemain.'
        ),
        'npc': (
            'NPC memiliki motivasi, emosi, dan pengetahuan sendiri. Nama pemain hanya diketahui narator; '
            'NPC tidak otomatis mengetahui nama atau informasi tersembunyi pemain.'
        ),
        'world': 'Bangun dunia yang masuk akal. Pertahankan aturan, tempat, benda, waktu, dan cuaca yang telah ditetapkan.',
        'style': STYLES[st.session_state.style] + '\n' + EXPRESSIONS[st.session_state.expression],
        'format': (
            FORMATS[st.session_state.action_format] + '\n'
            '*Perempuan itu menoleh.*\n"Ah, kau mengejutkanku!"\n'
            'Jangan membungkus dialog dengan tanda bintang.'
        ),
        'memory': 'Pertahankan nama, hubungan, kronologi, dan fakta dari riwayat yang tersedia.',
        'consequence': (
            'Reaksikan tindakan pemain secara wajar. Jangan menganggap setiap percobaan otomatis berhasil. '
            'Jangan memaksakan pilihan atau mengakhiri setiap respons dengan pertanyaan.'
        ),
        'validation': ('Tindakan pemain adalah usaha, bukan hasil pasti. Klaim kemampuan baru perlu dasar dari persona, riwayat, atau pembuktian. Berikan konsekuensi dan peluang berkembang yang masuk akal.'),
        'extra': '',
    }


def compose_sections(fields):
    return '\n\n'.join(
        f'[{label.upper()}]\n{fields.get(key, "").strip()}'
        for key, label in PROMPT_SECTIONS if fields.get(key, '').strip()
    )


def normalize_sections(fields):
    """Fill missing section keys from defaults; preserve intentionally empty entries."""
    defaults = default_sections()
    if not isinstance(fields, dict):
        fields = {}
    return {key: fields.get(key, defaults.get(key, '')) for key, _ in PROMPT_SECTIONS}


def initialize_studio(force=False):
    """Canonical drafts are independent of widget lifecycle and page navigation."""
    mode = st.session_state.mode
    if force:
        fields = default_sections()
    elif st.session_state.studio_mode != mode:
        fields = st.session_state.drafts_by_mode.get(mode)
        if fields is None:
            fields = default_sections()
    else:
        fields = st.session_state.studio_fields
        if not fields:
            fields = st.session_state.drafts_by_mode.get(mode) or default_sections()
    fields = normalize_sections(fields)
    st.session_state.studio_fields = dict(fields)
    st.session_state.studio_mode = mode
    st.session_state.drafts_by_mode[mode] = dict(fields)


def save_studio_field(section_key):
    """Only save the changed field: other widget keys may have been cleaned up."""
    widget_key = f'studio_{section_key}'
    if widget_key in st.session_state:
        value = st.session_state[widget_key]
        st.session_state.studio_fields[section_key] = value
        st.session_state.drafts_by_mode[st.session_state.mode] = dict(st.session_state.studio_fields)


def restore_studio_widgets():
    """Before rendering, always rehydrate from canonical draft, not stale widgets."""
    for key, _ in PROMPT_SECTIONS:
        st.session_state[f'studio_{key}'] = st.session_state.studio_fields.get(key, '')


def apply_studio():
    # Read from canonical draft; text-area on_change persists each edited field.
    fields = normalize_sections(st.session_state.studio_fields)
    merged = compose_sections(fields)
    if not merged.strip():
        st.session_state.notice = 'Isi setidaknya satu bagian prompt.'
        return
    st.session_state.studio_fields = dict(fields)
    st.session_state.drafts_by_mode[st.session_state.mode] = dict(fields)
    st.session_state.applied_by_mode[st.session_state.mode] = merged
    st.session_state.prompt_override = merged
    st.session_state.prompt_editor = merged
    st.session_state.notice = 'Prompt diterapkan. Riwayat tetap tersimpan; instruksi baru berlaku untuk pesan berikutnya.'


def reset_studio():
    initialize_studio(force=True)
    st.session_state.notice = 'Draft kembali ke default; prompt aktif tidak berubah sampai Terapkan ditekan.'


def api_key():
    # Session only: never read API keys from scripts, secrets.toml, or environment.
    if st.session_state.api_connected:
        return st.session_state.pollinations_key
    return ''


def disconnect_api():
    st.session_state.pollinations_key = ''
    st.session_state.api_connected = False
    st.session_state.api_key_input = ''
    st.session_state.api_notice = 'Koneksi diputus. Semua riwayat chat tetap tersimpan.'


def connect_api():
    candidate = st.session_state.api_key_input.strip()
    if not candidate:
        st.session_state.api_notice = 'Masukkan API key terlebih dahulu.'
        return
    # Use a minimal real request to verify authentication. This may consume tokens.
    # Never display raw server responses, request headers, or the supplied key.
    try:
        timeout = httpx.Timeout(connect=10, read=30, write=10, pool=10)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f'{BASE_URL}/chat/completions',
                headers={'Authorization': f'Bearer {candidate}', 'Content-Type': 'application/json'},
                json={'model': AGENTS[st.session_state.agent]['model'],
                      'messages': [{'role': 'user', 'content': 'Jawab hanya: OK'}],
                      'max_tokens': 12, 'stream': False},
            )
        if response.status_code == 200:
            data = response.json()
            if not data.get('choices'):
                raise ValueError('missing choices')
            st.session_state.pollinations_key = candidate
            st.session_state.api_connected = True
            st.session_state.api_key_input = ''
            st.session_state.api_notice = 'Koneksi berhasil. Chat dan Model Lab siap digunakan.'
        elif response.status_code in (401, 403):
            st.session_state.api_notice = 'API key ditolak (HTTP 401/403). Periksa key atau izin akses model.'
        else:
            st.session_state.api_notice = (
                f'Validasi belum berhasil (HTTP {response.status_code}). '
                'Bisa disebabkan kuota, model tidak tersedia, atau gangguan layanan.'
            )
    except (httpx.RequestError, ValueError, KeyError, TypeError):
        st.session_state.api_notice = 'Validasi koneksi gagal. Periksa jaringan dan coba lagi.'


def call_model(model_key, messages):
    key = api_key()
    if not key:
        raise RuntimeError('Hubungkan API key Pollinations melalui sidebar terlebih dahulu.')
    timeout = httpx.Timeout(connect=15, read=120, write=15, pool=15)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f'{BASE_URL}/chat/completions',
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                json={'model': AGENTS[model_key]['model'], 'messages': messages, 'stream': False},
            )
    except httpx.RequestError as exc:
        raise RuntimeError(f'Koneksi Pollinations gagal: {type(exc).__name__}') from exc
    if response.status_code != 200:
        raise RuntimeError(f'Pollinations HTTP {response.status_code}. Periksa izin model, kuota, atau status layanan.')
    try:
        content = response.json()['choices'][0]['message']['content']
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError('Format respons Pollinations tidak dikenali.') from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError('Model tidak mengembalikan jawaban teks.')
    return content.strip()



ACTION_POLICIES = {
    'Bebas': ('Utamakan improvisasi kreatif. Pemain boleh memperkenalkan kemampuan spontan, tetapi hasilnya tetap mengikuti logika dunia dan tidak otomatis mengatasi semua konflik.'),
    'Seimbang': (
        'Pisahkan niat/tindakan yang ditulis pemain dari hasil yang diputuskan narator. '
        'Klaim seperti "aku mengeluarkan sihir", "aku ahli", atau "aku langsung menang" bukan bukti otomatis kemampuan atau keberhasilan. '
        'Periksa persona, riwayat, aturan dunia, persiapan, kondisi, dan risiko. '
        'Kemampuan yang belum diketahui bukan berarti pasti tidak dimiliki: izinkan pembuktian, usaha terbatas, atau penemuan masuk akal. '
        'Hasil dapat berhasil, berhasil sebagian, gagal, atau menimbulkan konsekuensi relevan. '
        'Jangan membuat pemain gagal terus-menerus; berikan petunjuk dan kemajuan nyata. '
        'Jangan menyelesaikan konflik besar terlalu mudah, tetapi jangan menunda penyelesaian secara artifisial.'
    ),
    'Ketat': (
        'Kemampuan khusus perlu dasar yang jelas dalam persona atau riwayat. '
        'Klaim pemain saja tidak membuktikan kemampuan. Upaya tanpa prasyarat dapat gagal atau hanya menghasilkan efek kecil yang wajar. '
        'Berikan jalur belajar atau memperoleh kemampuan melalui cerita, tanpa mengambil alih keputusan pemain.'
    ),
}


def action_policy_prompt():
    if st.session_state.mode != 'Roleplay':
        return ''
    return ('[VALIDASI TINDAKAN AKTIF]\n' + ACTION_POLICIES[st.session_state.action_policy]
            + '\nHormati kendali pemain atas dialog, pilihan, dan tindakannya sendiri.')


def action_policy_changed():
    st.session_state.action_policy = st.session_state.action_policy_editor
    st.session_state.notice = 'Validasi tindakan diperbarui tanpa menghapus riwayat.'


def payload(history):
    result = []
    system_text = effective_prompt()
    if st.session_state.mode == 'Roleplay':
        system_text += '\n\n' + action_policy_prompt() + '\n\n' + character_context()
    if system_text.strip():
        result.append({'role': 'system', 'content': system_text})
    return result + history[-40:]


def render_message(content):
    if st.session_state.mode == 'Roleplay' and st.session_state.action_format == 'Bintang literal':
        st.text(content)
    else:
        st.markdown(content)


def navigate_to(destination):
    st.session_state.workspace = destination


# Workspace: navigation lives in the sidebar, editors live in the main panel.
initialize_studio()
PAGES = [
    '💬 Chat AI', '👥 Karakter & Persona', '🧩 Prompt Studio',
    '🌍 World Studio', '🧠 Memori & State', '⚖️ Model Lab', '📁 Sesi & Data',
]

with st.sidebar:
    st.title('🤖 Nusantara AI Lab')
    st.caption('Workspace v0.5.9')
    with st.expander('🔑 Koneksi Pollinations API', expanded=not st.session_state.api_connected):
        if st.session_state.api_connected:
            st.success('🟢 Terhubung')
            st.button('Putuskan Koneksi', on_click=disconnect_api, use_container_width=True)
        else:
            st.text_input('API key', type='password', key='api_key_input',
                          placeholder='Masukkan API key Pollinations')
            st.button('🔌 Hubungkan & Validasi', on_click=connect_api,
                      use_container_width=True, type='primary')
            st.caption('Validasi mengirim satu permintaan singkat ke model aktif dan mungkin menggunakan kuota.')
        if st.session_state.api_notice:
            st.caption(st.session_state.api_notice)
    st.divider()
    st.radio('Navigasi', PAGES, key='workspace', label_visibility='collapsed')
    st.divider()
    st.caption('PENGATURAN CEPAT')
    st.selectbox('Mode interaksi', ['Assistant', 'Roleplay'], key='mode', on_change=mode_changed)
    st.selectbox('Model utama', list(AGENTS), format_func=lambda k: AGENTS[k]['name'],
                 key='agent', on_change=model_changed)
    st.button('➕ New Chat', use_container_width=True, on_click=new_chat)
    st.caption('Mengganti menu tidak menghapus chat.')
    st.caption('Setiap model menyimpan riwayatnya sendiri. New Chat hanya mereset model aktif.')

page = st.session_state.workspace

if page == '🧩 Prompt Studio':
    restore_studio_widgets()
    st.title('🧩 Prompt Studio')
    st.caption('Buka tiap bagian untuk mengedit. Perubahan teks aktif setelah Terapkan ditekan.')
    if st.session_state.mode == 'Roleplay':
        st.session_state.action_policy_editor = st.session_state.action_policy
        st.selectbox('Validasi tindakan pemain', list(ACTION_POLICIES), key='action_policy_editor',
                     on_change=action_policy_changed,
                     help='Bebas: improvisasi; Seimbang: usaha dan konsekuensi; Ketat: kemampuan perlu dasar.')
        st.caption('Mode validasi langsung berlaku pada respons berikutnya tanpa menghapus chat.')
    if st.session_state.mode == 'Roleplay':
        st.session_state.player_editor = st.session_state.player
        with st.expander('Pengaturan gaya Roleplay', expanded=False):
            sync_player_widget('player_editor')
            st.text_input('Nama pemain', key='player_editor', on_change=player_changed)
            st.selectbox('Gaya Roleplay', list(STYLES), key='style', on_change=setting_changed)
            st.selectbox('Intensitas ekspresi', list(EXPRESSIONS), key='expression', on_change=setting_changed)
            st.selectbox('Tampilan tindakan', list(FORMATS), key='action_format', on_change=setting_changed)
            st.caption('Mengubah gaya tidak menghapus draft atau riwayat. Terapkan kembali prompt jika perlu.')
    for key, label in PROMPT_SECTIONS:
        with st.expander(label, expanded=False):
            st.text_area(label, key=f'studio_{key}', height=135, label_visibility='collapsed',
                         on_change=save_studio_field, args=(key,))
    draft = dict(st.session_state.studio_fields)
    with st.expander('🔎 Pratinjau gabungan prompt'):
        st.code(compose_sections(draft), language=None)
    col_apply, col_reset = st.columns(2)
    with col_apply:
        st.button('✅ Gabungkan & Terapkan Prompt', type='primary',
                  use_container_width=True, on_click=apply_studio)
    with col_reset:
        st.button('↩️ Reset Draft ke Default', use_container_width=True, on_click=reset_studio)
    st.download_button('⬇️ Unduh preset Prompt Studio (JSON)',
                       data=json.dumps({'mode': st.session_state.mode, 'sections': draft},
                                       ensure_ascii=False, indent=2),
                       file_name='nusantara_prompt_studio.json', mime='application/json')
    with st.expander('Prompt aktif yang dikirim ke model'):
        st.code(effective_prompt() + ('\n\n' + action_policy_prompt() if st.session_state.mode == 'Roleplay' else ''), language=None)

elif page == '👥 Karakter & Persona':
    st.title('👥 Karakter & Persona')
    if st.session_state.mode != 'Roleplay':
        st.info('Editor karakter tersedia dalam mode Roleplay. Pilih Roleplay di sidebar.')
    else:
        st.caption('Profil pemain dan NPC disimpan selama sesi. Perubahan profil berlaku pada pesan berikutnya tanpa menghapus chat.')
        tab_player, tab_npcs = st.tabs(['🧑 Karakter Pemain', '👥 Daftar NPC'])
        with tab_player:
            character_editor(PLAYER_FIELDS, 'profile_player', st.session_state.player_profile,
                             save_player_field, ())
            st.caption('Umur boleh berupa angka atau deskripsi; jenis kelamin dapat diisi bebas.')
        with tab_npcs:
            st.button('➕ Tambah NPC', on_click=add_npc, type='primary')
            npcs = st.session_state.npc_profiles
            if not npcs:
                st.info('Belum ada NPC khusus. AI masih boleh membuat NPC spontan berdasarkan cerita.')
            else:
                st.caption(f'{len(npcs)} NPC tersimpan. Pilih karakter untuk mengedit.')
                for npc in npcs:
                    title = npc.get('name', '').strip() or f'NPC {npc["id"]}'
                    col_name, col_edit = st.columns([4, 1])
                    with col_name:
                        st.write(f'**{title}** — {npc.get("role") or "Belum ada peran"}')
                    with col_edit:
                        st.button('Edit', key=f'edit_npc_{npc["id"]}',
                                  on_click=select_npc, args=(npc['id'],))
                selected = next((n for n in npcs if n['id'] == st.session_state.selected_npc_id), None)
                if selected is not None:
                    st.divider()
                    st.subheader('Edit ' + (selected.get('name') or 'NPC'))
                    character_editor(NPC_FIELDS, f'profile_npc_{selected["id"]}', selected,
                                     save_npc_field, (selected['id'],))
                    st.button('🗑️ Hapus NPC ini', on_click=delete_npc,
                              args=(selected['id'],), key=f'delete_npc_{selected["id"]}')
        with st.expander('🔎 Konteks karakter yang dikirim ke AI'):
            st.code(character_context(), language=None)
        st.caption('Tidak perlu menyalin profil karakter ke Prompt Studio. Profil digabungkan otomatis saat mengirim pesan.')

elif page == '🌍 World Studio':
    st.title('🌍 World Studio')
    st.info('Editor dunia terstruktur belum aktif. Untuk sementara, gunakan bagian World Lore di Prompt Studio.')
    st.button('Buka Prompt Studio', on_click=navigate_to, args=('🧩 Prompt Studio',))

elif page == '🧠 Memori & State':
    st.title('🧠 Memori & State')
    st.caption('Inspeksi riwayat saat ini; belum ada memori permanen atau status NPC otomatis.')
    if st.session_state.compare_mode:
        for model, branch in st.session_state.branches.items():
            st.metric(AGENTS[model]['name'], f'{len(branch)} pesan')
            with st.expander(f'Riwayat {AGENTS[model]["name"]}'):
                st.json(branch)
    else:
        st.metric('Jumlah pesan model aktif', len(current_history(st.session_state.agent)))
        with st.expander('Lihat riwayat model aktif'):
            st.json(current_history(st.session_state.agent))
    st.caption('Maksimal 40 pesan terakhir per jalur dikirim ke API; ini bukan memori jangka panjang.')

elif page == '⚖️ Model Lab':
    st.title('⚖️ Model Lab')
    st.caption('Konfigurasi perbandingan. Jalankan percakapan pada menu Chat AI.')
    if not api_key():
        st.info('Hubungkan API Pollinations di sidebar untuk menjalankan perbandingan model.')
    st.checkbox('Bandingkan dua model', key='compare_mode', on_change=model_changed)
    if st.session_state.compare_mode:
        st.selectbox('Model pembanding', list(AGENTS),
                     format_func=lambda k: AGENTS[k]['name'], key='compare_agent',
                     on_change=model_changed)
        if st.session_state.agent == st.session_state.compare_agent:
            st.warning('Pilih model pembanding yang berbeda dari model utama.')
        else:
            st.success(f"Model utama: {AGENTS[st.session_state.agent]['name']} | "
                       f"Pembanding: {AGENTS[st.session_state.compare_agent]['name']}")
    st.metric('Giliran perbandingan', len(st.session_state.comparisons))
    st.button('Buka Chat AI', on_click=navigate_to, args=('💬 Chat AI',))

elif page == '📁 Sesi & Data':
    st.title('📁 Sesi & Data')
    st.caption('Ekspor seluruh riwayat model tersedia di bawah. Impor sesi belum tersedia.')
    st.button('➕ Mulai Chat Baru', on_click=new_chat)
    st.metric('Jumlah perbandingan', len(st.session_state.comparisons))
    st.caption('Riwayat dan profil karakter tersimpan selama sesi browser Streamlit aktif; belum permanen.')

elif page == '💬 Chat AI':
    st.title('💬 Chat AI')
    st.caption(f"Mode: {st.session_state.mode} | Model: {AGENTS[st.session_state.agent]['name']}")
    if st.session_state.mode == 'Roleplay':
        st.caption(f"Pemain: {st.session_state.player} | Gaya: {st.session_state.style} | Validasi: {st.session_state.action_policy}")
        focus_options = ['Otomatis (sesuai adegan)'] + [n['name'].strip() for n in st.session_state.npc_profiles if n.get('name', '').strip()]
        if st.session_state.npc_focus not in focus_options:
            st.session_state.npc_focus = focus_options[0]
        st.selectbox('Fokus NPC (opsional)', focus_options, key='npc_focus',
                     help='Memprioritaskan NPC dalam adegan, tidak memindahkannya secara ajaib ke lokasi pemain.')
    if st.session_state.notice:
        st.info(st.session_state.notice)
        st.session_state.notice = ''
    if not api_key():
        st.warning('Chat terkunci. Masukkan API key Pollinations dan tekan Hubungkan & Validasi di sidebar.')

    valid_comparison = st.session_state.compare_mode and st.session_state.agent != st.session_state.compare_agent
    if valid_comparison:
        primary, secondary = st.session_state.agent, st.session_state.compare_agent
        st.session_state.branches[primary] = current_history(primary)
        st.session_state.branches[secondary] = current_history(secondary)
        st.caption('🔀 Kedua model memiliki riwayat percakapan independen.')
        for i, item in enumerate(st.session_state.comparisons, 1):
            if (item['primary'], item['secondary']) != (primary, secondary):
                continue
            with st.chat_message('user'):
                render_message(item['prompt'])
            left, right = st.columns(2)
            for column, model, answer_key, error_key in (
                (left, item['primary'], 'primary_answer', 'primary_error'),
                (right, item['secondary'], 'secondary_answer', 'secondary_error'),
            ):
                with column:
                    st.markdown(f"**{AGENTS[model]['name']}**")
                    if item[answer_key] is not None:
                        render_message(item[answer_key])
                    else:
                        st.warning('Belum berhasil merespons.')
                    if item.get(error_key):
                        st.error(item[error_key])
            st.divider()
    else:
        for item in current_history(st.session_state.agent):
            with st.chat_message(item['role']):
                render_message(item['content'])

    prompt = st.chat_input('Ketik pesan atau tindakan roleplay...',
                           disabled=(not api_key()) or (st.session_state.compare_mode and not valid_comparison))
    if prompt:
        user_message = {'role': 'user', 'content': prompt}
        if valid_comparison:
            answers, errors = {}, {}
            with st.spinner('Menghubungi kedua model secara independen...'):
                for model in (primary, secondary):
                    branch = st.session_state.branches[model]
                    try:
                        answer = call_model(model, payload(branch + [user_message]))
                        branch.extend([user_message.copy(), {'role': 'assistant', 'content': answer}])
                        answers[model] = answer
                    except RuntimeError as exc:
                        answers[model] = None
                        errors[model] = str(exc)
            st.session_state.comparisons.append({
                'prompt': prompt, 'primary': primary, 'secondary': secondary,
                'primary_answer': answers[primary], 'secondary_answer': answers[secondary],
                'primary_error': errors.get(primary), 'secondary_error': errors.get(secondary),
            })
            st.rerun()
        else:
            with st.chat_message('user'):
                render_message(prompt)
            with st.chat_message('assistant'):
                with st.spinner('AI sedang merespons...'):
                    try:
                        answer = call_model(st.session_state.agent, payload(current_history(st.session_state.agent) + [user_message]))
                        render_message(answer)
                        current_history(st.session_state.agent).extend([user_message, {'role': 'assistant', 'content': answer}])
                    except RuntimeError as exc:
                        st.error(str(exc))
                        st.info('Pesan gagal dikirim. Silakan kirim kembali.')

export = {
    'app': 'Nusantara AI Lab v0.5.9', 'exported_at': datetime.now(timezone.utc).isoformat(),
    'mode': st.session_state.mode, 'agent': AGENTS[st.session_state.agent]['model'],
    'compare_mode': st.session_state.compare_mode,
    'compare_agent': AGENTS[st.session_state.compare_agent]['model'] if st.session_state.compare_mode else None,
    'player': st.session_state.player if st.session_state.mode == 'Roleplay' else None,
    'style': st.session_state.style, 'expression': st.session_state.expression,
    'action_format': st.session_state.action_format, 'action_policy': st.session_state.action_policy, 'system_prompt': effective_prompt(),
    'messages': current_history(st.session_state.agent), 'model_histories': st.session_state.model_histories, 'comparisons': st.session_state.comparisons,
    'branches': {AGENTS[k]['model']: v for k, v in st.session_state.branches.items()},
    'prompt_sections': dict(st.session_state.studio_fields),
    'player_profile': dict(st.session_state.player_profile),
    'npc_profiles': [dict(n) for n in st.session_state.npc_profiles],
}
if page == '📁 Sesi & Data':
    st.download_button('⬇️ Ekspor percakapan JSON',
                       data=json.dumps(export, ensure_ascii=False, indent=2),
                       file_name='nusantara_ai_lab_v059_export.json',
                       mime='application/json', use_container_width=True)
