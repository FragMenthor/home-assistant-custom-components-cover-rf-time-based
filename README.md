# Cover Time Based Sync

Integração personalizada para o Home Assistant que controla portões, estores ou qualquer cover baseada em tempo.  
Suporta dois modos de controlo: **Standard** (scripts abrir/fechar/parar) e **Controlo Único (RF)** com apenas um botão/pulso.

Inclui sensores de contacto opcionais (aberto/fechado) para confirmar a posição real.

---

## Funcionalidades

### Movimento baseado em tempo
- Define tempos de subida e descida (0–100%).
- Atualiza automaticamente a posição durante o movimento.

### Modo Standard (scripts tradicionais)
- Pode indicar até três scripts:
  - `open_script_entity_id` (abrir)
  - `close_script_entity_id` (fechar)
  - `stop_script_entity_id` (parar)

### Controlo Único (RF)
- Ideal para motores RF com **um só botão ou comando**.
- Usa **um único script** (“RF pulse script”).
- Alterna automaticamente ações e prevê a próxima ação:
  - sequência típica: `abrir → parar → fechar → parar → abrir → ...`
- A próxima ação fica exposta em `single_control_next_action`.

### Sensores de contacto (opcionais)
- **Fechado** (`binary_sensor` ON) → posição confirmada **0%**.
- **Aberto** (`binary_sensor` ON) → posição confirmada **100%**.
- Cancela o movimento atual e ajusta a próxima ação.

### Opções adicionais
- `send_stop_at_ends` → envia `stop` ao atingir **0%/100%**.
- `smart_stop_midrange` → para automaticamente em alvos intermédios (20–80%).
- `always_confident` → assume posição como confiável.

---

## Instalação

1. Copie a pasta para:
  - `custom_components/cover_time_based_sync/`
2. Reinicie o Home Assistant.
3. Vá a **Definições → Dispositivos e Serviços → Adicionar Integração**.
4. Procure **Cover Time Based Sync**.

---

## Configuração (UI)

A configuração tem **2 passos**:

### Passo 1: Escolher o modo
- Ativar/desativar **Controlo Único (RF)**.
- Definir **atraso entre pulsos (ms)**.

### Passo 2A: Controlo Único (RF)
Mostra apenas:
- **Script RF (pulsar)**.
- Tempos de subida/descida.
- Sensores de contacto (opcionais).
- Opções (stop nos extremos, midrange, confiança, aliases).

### Passo 2B: Modo Standard
Mostra:
- Scripts de **abrir/fechar/parar**.
- Tempos de subida/descida.
- Sensores de contacto (opcionais).
- Opções (stop nos extremos, midrange, confiança, aliases).

---

## Atributos expostos

| Atributo                           | Descrição                                         |
|-----------------------------------|---------------------------------------------------|
| `current_position`                | Posição calculada (0–100%)                        |
| `position_confident`              | Posição confirmada (true/false)                   |
| `single_control_enabled`          | Modo RF ativo                                     |
| `single_control_rf_script_entity_id` | Script usado para pulso RF                     |
| `single_control_next_action`      | Próxima ação prevista (`open` / `close` / `stop`) |
| `travelling_time_up`              | Tempo de subida (s)                               |
| `travelling_time_down`            | Tempo de descida (s)                              |
| `send_stop_at_ends`               | Envia `stop` nos extremos                         |
| `smart_stop_midrange`             | Envia `stop` em alvos intermédios                 |
| `aliases`                         | Lista de nomes alternativos (CSV)                 |

---

## Serviços

### `cover_time_based_sync.set_known_position`
Define a posição **atual** ou mover para um **alvo**.
```yaml
service: cover_time_based_sync.set_known_position
target:
entity_id: cover.portao
data:
position: 0
confident: true
position_type: current
```

### `cover_time_based_sync.set_known_action`
Executa uma ação direta: **open**, **close**, **stop**.
```yaml
service: cover_time_based_sync.set_known_action
target:
  entity_id: cover.portao
data:
  action: open
```

### `cover_time_based_sync.activate_script`
Executa o script correspondente: **single**, **open**, **close**, **stop**.
```yaml
service: cover_time_based_sync.activate_script
target:
  entity_id: cover.portao
```
or
```yaml
service: cover_time_based_sync.activate_script
target:
  entity_id: cover.portao
data:
  action: close
```

---

Estrutura de pastas
```
custom_components/cover_time_based_sync/
├── __init__.py
├── cover.py
├── config_flow.py
├── const.py
├── manifest.json
├── services.yaml
├── travelcalculator.py
└── translations/
    ├── en.json
    └── pt.json
```

---

## Recomendações
- Calibrar tempos de subida/descida para maior precisão.
- Usar sensores de contacto quando possível.
- No modo RF, garantir que o script executa um único pulso por chamada.
- Após atualizar ficheiros, limpar __pycache__ e reiniciar o Home Assistant.

---

## Licença
- Este projeto segue a licença definida no repositório original ou pelo autor.
