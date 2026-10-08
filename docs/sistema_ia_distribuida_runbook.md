# Sistema de IA Distribuída com Raspberry Pi + Android/Termux

> Runbook de instalação, avaliação, recuperação e estado atual  
> Estado documentado: 2026-10-07  
> Objetivo: tornar a instalação reproduzível a partir de hardware Android reaproveitado, com Raspberry Pi como plano de controlo e telefones como workers de inferência.

---

## 1. Objetivo e princípios

O sistema foi desenhado para aproveitar dois telefones Android como appliances de inferência local e um Raspberry Pi como orquestrador.

Princípios acordados:

- O **Raspberry Pi é o plano de controlo**.
- Cada telefone Android é um **worker independente de inferência**.
- O LLM **propõe** alterações; ferramentas determinísticas **verificam**.
- Git protege o estado do projeto.
- Testes, lint, typecheck e regras explícitas decidem se uma alteração é aceite.
- O LLM não recebe shell irrestrito nem o repositório inteiro por defeito.
- Contexto enviado ao modelo deve ser mínimo e orientado à tarefa.
- O orquestrador aplica patches e executa verificações.
- Comandos executáveis pelo futuro orquestrador devem ser allowlisted/sandboxed.
- Sem segredos de produção nos workers.
- Sem `push` direto para `main` pelos workers.
- Iterações, número de ficheiros, tamanho de diff e tempo de execução devem ter limites.
- Todo o código Python do projeto será escrito pelo utilizador; o sistema/orquestrador deve trabalhar com contratos, interfaces, invariantes e testes explícitos.

### 1.1 Arquitetura física atual

```text
                              REDE LOCAL / TAILNET

       +-------------------+                    +-------------------+
       |   PC / portátil   |                    |   Raspberry Pi    |
       | bootstrap / debug |                    |  control plane    |
       +---------+---------+                    +---------+---------+
                 |                                        |
        USB/ADB  | (apenas bootstrap)                     | SSH / HTTP
                 |                                        |
                 v                                        v
       +---------+---------+                    +----------+---------+
       | Android / Termux  |                    | Android / Termux   |
       | Huawei P30 Lite NE|                    | OPPO Reno4 Z 5G    |
       | worker lento      |                    | worker principal   |
       +-------------------+                    +--------------------+

ADB não faz parte do caminho de produção.
Após bootstrap, administração = SSH; inferência = HTTP do llama-server.
```

### 1.2 Arquitetura lógica pretendida

```text
                         +--------------------------+
                         |       UTILIZADOR         |
                         +------------+-------------+
                                      |
                                      v
                         +------------+-------------+
                         |       RASPBERRY PI       |
                         |--------------------------|
                         | Git / worktrees          |
                         | task queue               |
                         | scheduler / state machine|
                         | SQLite / project DB      |
                         | worker registry          |
                         | retrieval                |
                         | ripgrep / Tree-sitter    |
                         | LSP                      |
                         | tests / lint / typecheck |
                         | notifications            |
                         +------+-------------+-----+
                                |             |
                        HTTP    |             | HTTP
                                v             v
                    +-----------+--+      +---+-----------+
                    | OPPO worker  |      | Huawei worker |
                    | llama-server |      | llama-server  |
                    +--------------+      +---------------+

Fluxo futuro de uma tarefa:

 task
   |
   v
 decomposição
   |
   v
 branch/worktree
   |
   v
 contexto mínimo
   |
   v
 chamada ao worker LLM
   |
   v
 patch estruturado
   |
   v
 aplicar patch
   |
   +--> format
   +--> lint
   +--> typecheck
   +--> tests
   |
   +--> falhou? --> erros + diff --> nova tentativa limitada
   |
   v
 review determinístico / humano
   |
   v
 commit
```

---

## 2. Inventário de hardware

### 2.1 OPPO — worker principal

| Campo | Valor observado |
|---|---|
| Modelo | OPPO CPH2065 / Reno4 Z 5G |
| SoC | MediaTek Dimensity 800 |
| CPU | 4x Cortex-A55 + 4x Cortex-A76 |
| Frequência máxima observada | até ~2 GHz |
| RAM | 8 GB |
| Armazenamento | 128 GB |
| Arquitetura Termux | `aarch64` |
| Papel | worker principal / tarefas de código com contexto maior |

### 2.2 Huawei — worker secundário

| Campo | Valor observado |
|---|---|
| Modelo | Huawei MAR-LX1B / P30 Lite New Edition |
| SoC | Kirin 710 |
| CPU 0-3 | Cortex-A53 @ 1.709 GHz |
| CPU 4-7 | Cortex-A73 @ 2.189 GHz |
| RAM | 6 GB |
| Armazenamento | 256 GB |
| Arquitetura Termux | `aarch64` |
| Papel | worker lento / tarefas pequenas, classificação, JSON, summaries curtos |

### 2.3 Raspberry Pi — plano de controlo

Estado observado:

```text
hostname/login: gabi@gabi
LAN:            192.168.1.100
Tailscale:      100.85.237.37
kernel visto:   Linux 6.1.21+, armv6l
```

O modelo exato do Raspberry Pi ainda não foi registado neste runbook. Numa reinstalação, capturar:

```sh
cat /proc/device-tree/model 2>/dev/null; echo
uname -a
free -h
df -h
```

---

## 3. Avaliação reproduzível do hardware Android

Executar **dentro do Termux de cada telefone**:

```sh
whoami
uname -m
getprop ro.product.manufacturer
getprop ro.product.model
getprop ro.product.device
getprop ro.build.version.release
getprop ro.build.version.sdk
```

CPU e clusters:

```sh
cat /proc/cpuinfo | grep -E 'processor|CPU implementer|CPU architecture|CPU part'
```

Frequências máximas por core:

```sh
for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
    echo -n "$(basename "$cpu"): "
    cat "$cpu/cpufreq/cpuinfo_max_freq" 2>/dev/null
done
```

Memória:

```sh
grep -E 'MemTotal|MemAvailable|SwapTotal|SwapFree' /proc/meminfo
free -h 2>/dev/null || true
```

Armazenamento:

```sh
df -h "$HOME"
du -sh "$HOME"/* 2>/dev/null | sort -h
```

Versão/origem do Termux:

```sh
termux-info | sed -n '/Termux Variables:/,/Packages CPU architecture:/p'
```

Nos dois aparelhos ficou confirmado:

```text
TERMUX_APP__APK_RELEASE=GITHUB
TERMUX_VERSION=0.119.0-beta.3
```

Isto é importante porque **Termux e Termux:Boot devem usar uma origem/assinatura compatível**.

---

## 4. Decisão do modelo

O modelo escolhido para os testes e para o estado atual é:

```text
Qwen2.5-Coder-1.5B-Instruct
quantização: Q4_K_M
formato: GGUF
ficheiro: qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
```

A página oficial do modelo reporta 1.54B parâmetros. O GGUF Q4_K_M oficial tem aproximadamente 1.12 GB e SHA-256:

```text
cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046
```

### 4.1 Tabela simples de decisão

| Modelo / classe | OPPO | Huawei | Decisão atual |
|---|---|---|---|
| Qwen2.5-Coder 0.5B Q4 | Deve ser muito leve; ainda não medido | Bom candidato para triage/classificação/JSON | Testar depois no Huawei |
| **Qwen2.5-Coder 1.5B Q4_K_M** | **Bom compromisso; ~12.6 tok/s de geração no melhor teste** | **Utilizável; ~5.5–6.8 tok/s conforme teste** | **Selecionado** |
| >=3B Q4 | Não benchmarkado; maior custo de RAM/contexto | Não recomendado sem benchmark específico | Adiar |

Critério usado: não escolher apenas pelo facto de caber em RAM. A decisão considera **prompt processing**, **token generation**, latência e função de cada worker.

---

## 5. Benchmarks observados

### 5.1 OPPO

Build observado numa fase dos testes:

```text
llama.cpp 0.6.0-dev
commit observado: 4f54067
```

Resultados com Qwen2.5-Coder-1.5B-Instruct Q4_K_M:

| Threads/configuração | pp512 (tok/s) | tg128 (tok/s) |
|---|---:|---:|
| 2 threads | 31.03 | 11.09 |
| 4 threads | 59.30 | 12.44 |
| 6 threads | 59.53 | 11.09 |
| 8 threads | 60.71 | 10.76 |
| 4 threads, fast cores, `-C f0 --cpu-strict 1` | **62.26** | **12.59** |
| cluster A55 | 18.07 | 6.86 |

Conclusão: quatro threads nos cores rápidos A76 deram a melhor relação desempenho/consumo. Aumentar para 6/8 threads quase não melhorou prompt processing e reduziu geração.

### 5.2 Huawei

Build observado:

```text
commit/build observado: a46709b
```

Durante a configuração, CMake não detetou dotprod/i8mm nesse aparelho/build.

| Teste | Prompt (tok/s) | Geração (tok/s) |
|---|---:|---:|
| p512 / n128, t4, `-C f0 --cpu-strict 1`, r3 | 7.54 | 5.49 |
| p64 / n32 | 9.67 | 6.82 |
| p256 / n32 | 9.70 | 6.81 |

Comparando o teste p512/n128, o OPPO ficou aproximadamente 8.3x mais rápido no prompt processing e 2.3x mais rápido na geração.

### 5.3 Comando de benchmark base

Executar no telefone, dentro de `~/llama.cpp`:

```sh
./build/bin/llama-bench \
  -m ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  -p 512 \
  -n 128 \
  -t 2,4,6,8 \
  -r 3
```

Teste orientado a quatro cores rápidos:

```sh
./build/bin/llama-bench \
  -m ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  -p 512 \
  -n 128 \
  -t 4 \
  -C f0 \
  --cpu-strict 1 \
  -r 3
```

**Nota:** flags de afinidade variam com versões do `llama.cpp`. O `--help` da build local é a autoridade final antes de repetir benchmarks.

---

## 6. Bootstrap inicial por ADB

ADB foi usado apenas para transformar um Android recém-preparado num host Termux acessível. Depois de SSH direto funcionar, ADB deixa de ser dependência operacional.

### 6.1 Preparação no Android

No telefone:

1. Ativar Developer Options.
2. Ativar USB debugging.
3. Ligar por USB ao PC.
4. Aceitar a fingerprint/chave ADB apresentada pelo Android.

No PC:

```sh
adb version
adb devices
```

Esperado:

```text
<serial>    device
```

### 6.2 Termux usado no projeto

APK observado no bootstrap:

```text
termux-app_v0.119.0-beta.3+apt-android-7-github-debug_universal.apk
```

Instalação:

```sh
adb install -r termux-app_v0.119.0-beta.3+apt-android-7-github-debug_universal.apk
```

Durante o bootstrap houve inicialmente:

```text
INSTALL_FAILED_VERIFICATION_FAILURE
```

Depois de permitir a instalação/verificação adequada no Android, o mesmo `adb install -r` terminou com `Success`.

### 6.3 Bootstrap histórico do OpenSSH via input ADB

Foi usado ADB para introduzir comandos no terminal Termux:

```sh
adb shell input text 'pkg%supdate%s-y'
adb shell input keyevent 66

adb shell input text 'pkg%sinstall%sopenssh%s-y'
adb shell input keyevent 66

adb shell input text 'passwd'
adb shell input keyevent 66
```

Isto é útil como bootstrap, mas é frágil. Numa reinstalação, é preferível abrir Termux manualmente e executar diretamente:

```sh
apt update
apt install openssh
passwd
```

### 6.4 SSH inicial só por loopback + túnel ADB

Durante bootstrap o daemon foi inicialmente limitado a loopback:

```sh
sshd -o ListenAddress=127.0.0.1
```

No PC:

```sh
adb forward tcp:8022 tcp:8022
```

Descobrir o utilizador Termux:

```sh
whoami
```

Exemplos observados:

```text
Huawei: u0_a192
OPPO:   u0_a241
```

Ligação inicial a partir do PC:

```sh
ssh -p 8022 u0_a192@127.0.0.1
```

Se a mesma combinação `127.0.0.1:8022` tiver sido usada anteriormente para outro telefone, o host key muda. Limpar apenas essa entrada:

```sh
ssh-keygen -R '[127.0.0.1]:8022'
```

Depois de o SSH direto por LAN estar confirmado, remover forwarding:

```sh
adb forward --remove-all
```

**Invariante:** ADB é ferramenta de bootstrap/recuperação, não transporte do sistema final.

---

## 7. Preparação do Termux

Executar em cada telefone.

### 7.1 Atualizar pacotes

```sh
apt update
apt upgrade
```

Instalar dependências principais:

```sh
apt install git cmake clang make curl libandroid-spawn openssh openssl
```

Versões observadas durante o setup incluíram:

```text
git   2.56.0
cmake 4.4.4
clang 21.1.8
target aarch64-unknown-linux-android24
```

### 7.2 Problema real: `pkg` dizia que todos os mirrors estavam indisponíveis

No OPPO aconteceu:

```text
Error: None of the mirrors are accessible
```

Apesar disso, este teste funcionava:

```sh
curl -I --max-time 10 \
  https://packages.termux.dev/apt/termux-main/dists/stable/InRelease
```

Resposta observada:

```text
HTTP/1.1 200 OK
```

A correção usada foi fixar o repositório oficial diretamente:

```sh
echo 'deb https://packages.termux.dev/apt/termux-main stable main' \
  > "$PREFIX/etc/apt/sources.list"
```

E usar `apt` diretamente:

```sh
apt update
apt upgrade
apt install termux-services
```

Não é necessário usar `sudo`/`su` no Termux normal. O ambiente não é root e `apt` no próprio prefixo do Termux funciona sem `sudo`.

---

## 8. Compilar `llama.cpp` no telefone

Executar em cada telefone:

```sh
cd ~
git clone --depth 1 https://github.com/ggml-org/llama.cpp
cd llama.cpp

cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j4
```

Verificar binários:

```sh
ls -lh build/bin/llama-server build/bin/llama-bench build/bin/llama-cli
```

### 8.1 Reprodutibilidade de versão

O comando histórico `git clone --depth 1` captura o `master` do momento e portanto **não é reprodutível a longo prazo**.

Commits observados nos testes:

```text
OPPO:   4f54067
Huawei: a46709b
```

Para reproduzir exatamente um build antigo, usar um clone que contenha o commit e fazer checkout explícito, por exemplo:

```sh
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
git checkout <COMMIT_ESCOLHIDO>
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j4
```

Antes de padronizar os dois telefones num único commit, repetir os benchmarks porque os resultados atuais vieram de builds diferentes.

---

## 9. Descarregar e verificar o modelo

Criar diretório:

```sh
mkdir -p ~/models
```

Download usado:

```sh
curl -L \
  -o ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
```

Verificar tamanho:

```sh
ls -lh ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
```

Verificar checksum:

```sh
sha256sum ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
```

Esperado para o ficheiro oficial consultado:

```text
cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046
```

---

## 10. `llama-server`: configuração testada

### 10.1 API key

Cada telefone deve possuir a sua própria chave.

```sh
mkdir -p ~/.config/llama
chmod 700 ~/.config/llama
openssl rand -hex 32 > ~/.config/llama/api.key
chmod 600 ~/.config/llama/api.key
```

Nunca copiar a chave real para documentação ou Git.

### 10.2 Runtime preferido no OPPO

```sh
cd ~/llama.cpp

./build/bin/llama-server \
  -m ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  -c 2048 \
  -t 4 \
  -tb 4 \
  -C f0 \
  --cpu-strict 1 \
  -np 1 \
  --host 0.0.0.0 \
  --port 8080 \
  --api-key-file ~/.config/llama/api.key
```

Resultado HTTP observado no OPPO: aproximadamente 12.1–12.4 tok/s em geração, compatível com os benchmarks locais.

### 10.3 Health check

Da Raspberry/LAN:

```sh
curl http://192.168.1.166:8080/health
```

Huawei:

```sh
curl http://192.168.1.66:8080/health
```

### 10.4 Teste autenticado

No próprio worker:

```sh
KEY="$(cat ~/.config/llama/api.key)"

curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [
      {"role": "user", "content": "Reply only with OK"}
    ],
    "max_tokens": 8
  }'
```

### 10.5 Segurança ainda por fechar

Num teste do Huawei, a chamada autenticada funcionou, mas posteriormente uma chamada LAN sem header de autenticação também conseguiu gerar resposta. Antes de transformar `llama-server` em serviço permanente, validar que existe apenas **um** processo e que a flag da API key está realmente aplicada.

Diagnóstico:

```sh
pgrep -af llama-server

for pid in $(pgrep -f llama-server); do
    tr '\0' ' ' < "/proc/$pid/cmdline"
    echo
done
```

Parar todos antes de um arranque limpo:

```sh
pkill -f llama-server
```

Verificar porta:

```sh
ss -ltn 2>/dev/null | grep ':8080' || true
```

Em Android sem root, `ss` pode responder `Cannot open netlink socket: Permission denied`; isso não implica que o servidor esteja parado.

Depois arrancar uma única instância com `--api-key-file` e confirmar:

```text
/health                 -> pode continuar público
/v1/chat/completions    -> sem token deve ser rejeitado
/v1/chat/completions    -> com token deve funcionar
```

**Este controlo de autenticação está pendente antes de produção.**

---

## 11. Rede

### 11.1 LAN atual

| Nó | LAN | SSH |
|---|---|---|
| Raspberry Pi | `192.168.1.100` | 22 |
| Huawei | `192.168.1.66` | 8022 |
| OPPO | `192.168.1.166` | 8022 |

### 11.2 Tailscale conhecido

| Nó | Tailscale observado |
|---|---|
| Raspberry Pi | `100.85.237.37` |
| Huawei | `100.120.103.54` |
| OPPO | `100.126.244.66` |

Decisão arquitetural: usar **Tailscale + MagicDNS** como caminho estável futuro entre control plane e workers, evitando dependência de leases DHCP ou DNS local do Pi-hole.

Estado atual: os aliases SSH do Raspberry ainda usam os IPs LAN. A troca para nomes/IPs Tailscale deve ser feita apenas depois de confirmar SSH Termux pela interface Tailscale com o telefone bloqueado e após reboot.

### 11.3 O que foi descartado

Foi investigada a hipótese de usar Pi-hole como DHCP/DNS para fixar workers. O estado observado do Pi-hole mostrou DHCP desativado e nenhuma lista de leases/hosts útil para este objetivo. A decisão foi **não tornar o cluster dependente do Pi-hole**.

Se existir ainda um nameserver global Tailscale apontado ao Pi-hole (`100.85.237.37`) com `Override local DNS`, rever essa configuração antes de declarar MagicDNS independente. Isto é uma tarefa de rede separada; não é requisito para o SSH LAN que está hoje funcional.

---

## 12. SSH permanente: Raspberry -> Android

### 12.1 Criar chave no Raspberry

No Raspberry:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
```

Foi usada passphrase na private key.

Ficheiros:

```text
/home/gabi/.ssh/id_ed25519
/home/gabi/.ssh/id_ed25519.pub
```

### 12.2 Copiar a public key

Huawei:

```sh
ssh-copy-id -i ~/.ssh/id_ed25519.pub -p 8022 u0_a192@192.168.1.66
```

OPPO:

```sh
ssh-copy-id -i ~/.ssh/id_ed25519.pub -p 8022 u0_a241@192.168.1.166
```

O ficheiro importante nos telefones é:

```text
~/.ssh/authorized_keys
```

`known_hosts` no Raspberry guarda as **host keys dos telefones**; não deve receber a public key do utilizador.

Fingerprints ECDSA observadas em 2026-10-07:

```text
Huawei [192.168.1.66]:8022
SHA256:1U3sywgyaiObZ0xsZ+MXC70oCAEirvNPgpwQeu5tHuE

OPPO [192.168.1.166]:8022
SHA256:2fboPFjkcMCMyjkgqv6fa49CR60tufT8+pTlGnSusKs
```

Verificação:

```sh
ssh-keygen -F '[192.168.1.66]:8022'
ssh-keygen -F '[192.168.1.166]:8022'
```

Reinstalar Termux/OpenSSH pode mudar host keys; nunca aceitar uma mudança inesperada sem perceber a causa.

---

## 13. Ficheiro `~/.ssh/config` no Raspberry

Ficheiro criado:

```text
/home/gabi/.ssh/config
```

Conteúdo atual:

```sshconfig
Host ai-huawei
    HostName 192.168.1.66
    User u0_a192
    Port 8022
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes

Host ai-oppo
    HostName 192.168.1.166
    User u0_a241
    Port 8022
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Permissões:

```sh
chmod 600 ~/.ssh/config
```

Uso:

```sh
ssh ai-huawei
ssh ai-oppo
```

**Nota:** `ai-huawei` é o alias correto. `ai-huawey` não existe.

---

## 14. `ssh-agent` no Raspberry

Para não introduzir a passphrase a cada ligação:

```sh
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
ssh-add -l
```

Validação:

```sh
ssh ai-oppo 'date'
ssh ai-huawei 'date'
```

---

## 15. `termux-services` / runit

### 15.1 Instalação

Em cada telefone:

```sh
apt update
apt install termux-services
```

Pacotes observados:

```text
runit 2.3.1
termux-services 0.13-1
```

Reabrir a shell ou carregar explicitamente:

```sh
source "$PREFIX/etc/profile.d/start-services.sh"
```

Verificar:

```sh
echo "$SVDIR"
pgrep -af runsvdir
```

Esperado:

```text
/data/data/com.termux/files/usr/var/service
.../bin/runsvdir /data/data/com.termux/files/usr/var/service
```

### 15.2 Ativar `sshd`

```sh
sv-enable sshd
sv status sshd
```

Serviço habilitado significa que **não** existe:

```text
$PREFIX/var/service/sshd/down
```

Verificação reproduzível:

```sh
test ! -e "$PREFIX/var/service/sshd/down" && echo SSHD_ENABLED
```

---

## 16. Problema real: `Address already in use` na porta 8022

Nos dois telefones existia inicialmente um `sshd` iniciado manualmente. Ao ativar o serviço runit, o novo `sshd` não conseguia ocupar 8022:

```text
Bind to port 8022 on :: failed: Address already in use.
Bind to port 8022 on 0.0.0.0 failed: Address already in use.
Cannot bind any address.
```

Diagnóstico:

```sh
pgrep -af sshd
tail -n 50 "$PREFIX/var/log/sv/sshd/current"
```

Exemplo de estado problemático:

```text
<PID_MANUAL> sshd
<PID> runsv sshd
<PID> svlogd .../var/log/sv/sshd
```

Não usar `pkill sshd` a partir da única sessão SSH. Identificar o PID do daemon manual e matar **apenas esse PID**:

```sh
kill <PID_MANUAL>
sleep 2
sv status sshd
pgrep -af sshd
```

Resultado esperado:

```text
run: sshd: (pid <NOVO_PID>) ...
<NOVO_PID> sshd -D -e
```

Isto prova que o runit assumiu a porta e passará a reiniciar o daemon se ele morrer.

---

## 17. Gotcha: `sv status` em comandos SSH não-interativos

Este comando:

```sh
ssh ai-oppo 'date; sv status sshd'
```

chegou a devolver:

```text
fail: sshd: unable to change to service directory: file does not exist
```

O SSH estava funcional; o problema era a shell não-interativa não ter `SVDIR` definido.

Usar:

```sh
ssh ai-oppo \
  'SVDIR=/data/data/com.termux/files/usr/var/service sv status sshd'
```

Ou, de forma portátil no Termux:

```sh
ssh ai-oppo 'SVDIR=$PREFIX/var/service sv status sshd'
```

Validação completa:

```sh
ssh ai-oppo '
echo "OPPO: $(date)"
pgrep -af runsvdir
SVDIR=$PREFIX/var/service sv status sshd
pgrep -af "sshd -D"
'
```

---

## 18. Android: manter o worker vivo com ecrã bloqueado

`termux-wake-lock` foi ativado:

```sh
termux-wake-lock
```

Mas wake lock sozinho não substitui as permissões de background do fabricante.

Configuração recomendada no Android para **Termux, Termux:Boot e Tailscale**:

- permitir execução em background;
- remover otimização de bateria / usar “sem restrições”;
- permitir auto-start/app launch quando a ROM oferecer essa opção;
- no Huawei/EMUI, manter rede ligada durante sleep;
- opcionalmente bloquear/fixar a app em Recent Apps quando disponível;
- evitar Power Saving Mode durante validação.

Teste feito no Huawei com ecrã bloqueado:

```sh
ping -c 5 192.168.1.66
ssh -vvv ai-huawei 'date'
```

Foi observado 0% packet loss e autenticação SSH por chave com sucesso. Isto permitiu separar problemas de sleep da configuração de boot.

---

## 19. Termux:Boot

### 19.1 Requisitos

Nos dois aparelhos:

```text
TERMUX_APP__APK_RELEASE=GITHUB
TERMUX_VERSION=0.119.0-beta.3
```

Portanto o Termux:Boot deve vir da **mesma família de assinatura/origem GitHub**.

Depois de instalar Termux:Boot:

1. abrir o ícone **Termux:Boot** pelo menos uma vez;
2. conceder/permitir background/autostart conforme a ROM;
3. retirar Termux e Termux:Boot das otimizações agressivas de bateria;
4. criar `~/.termux/boot/`.

---

## 20. Primeiro ficheiro de boot criado — substituído

Ficheiro inicial:

```text
~/.termux/boot/00-start-services
```

Conteúdo:

```sh
#!/data/data/com.termux/files/usr/bin/sh

termux-wake-lock
source /data/data/com.termux/files/usr/etc/profile.d/start-services.sh
```

Permissão:

```sh
chmod 700 ~/.termux/boot/00-start-services
```

Embora este seja um padrão suportado pelo Termux:Boot/termux-services, nos testes os dois telefones regressavam à rede após reboot mas a porta 8022 ficava em `Connection refused`. Para diagnosticar e tornar o arranque explícito, este ficheiro foi substituído.

---

## 21. Ficheiro de boot final validado

Ficheiro final:

```text
~/.termux/boot/00-worker-boot
```

Conteúdo **validado nos dois telefones após reboot**:

```sh
#!/data/data/com.termux/files/usr/bin/sh

PREFIX=/data/data/com.termux/files/usr
HOME=/data/data/com.termux/files/home
SVDIR="$PREFIX/var/service"
LOGDIR="$PREFIX/var/log"

export PREFIX HOME SVDIR LOGDIR

exec >> "$HOME/worker-boot.log" 2>&1

echo "===== BOOT $(date) ====="

termux-wake-lock

echo "starting service-daemon..."
"$PREFIX/bin/service-daemon" start

sleep 3

echo "runsvdir:"
pgrep -af runsvdir || true

echo "starting sshd through runit..."
"$PREFIX/bin/sv" up sshd

sleep 2

echo "sshd status:"
"$PREFIX/bin/sv" status sshd

echo "processes:"
pgrep -af sshd || true
```

Instalação:

```sh
mkdir -p ~/.termux/boot

cat > ~/.termux/boot/00-worker-boot <<'EOF_BOOT'
#!/data/data/com.termux/files/usr/bin/sh

PREFIX=/data/data/com.termux/files/usr
HOME=/data/data/com.termux/files/home
SVDIR="$PREFIX/var/service"
LOGDIR="$PREFIX/var/log"

export PREFIX HOME SVDIR LOGDIR

exec >> "$HOME/worker-boot.log" 2>&1

echo "===== BOOT $(date) ====="

termux-wake-lock

echo "starting service-daemon..."
"$PREFIX/bin/service-daemon" start

sleep 3

echo "runsvdir:"
pgrep -af runsvdir || true

echo "starting sshd through runit..."
"$PREFIX/bin/sv" up sshd

sleep 2

echo "sshd status:"
"$PREFIX/bin/sv" status sshd

echo "processes:"
pgrep -af sshd || true
EOF_BOOT

chmod 700 ~/.termux/boot/00-worker-boot
rm -f ~/.termux/boot/00-start-services
```

### 21.1 Teste manual antes de reboot

```sh
~/.termux/boot/00-worker-boot
tail -n 50 ~/worker-boot.log
```

### 21.2 Log real de sucesso no OPPO

Exemplo observado depois de reboot:

```text
===== BOOT Wed Oct  7 07:28:21 WEST 2026 =====
starting service-daemon...
Starting daemon: service-daemon.
runsvdir:
7636 /data/data/com.termux/files/usr/bin/runsvdir /data/data/com.termux/files/usr/var/service
starting sshd through runit...
sshd status:
run: sshd: (pid 7642) 5s; run: log: (pid 7640) 5s
processes:
7639 runsv sshd
7640 svlogd -tt /data/data/com.termux/files/usr/var/log/sv/sshd
7642 sshd -D -e
```

O utilizador confirmou posteriormente que **OPPO e Huawei passaram o teste de reboot**.

---

## 22. Teste final de boot headless

Reiniciar um telefone de cada vez.

Não abrir Termux manualmente após o reboot.

No Raspberry, OPPO:

```sh
ping -c 3 192.168.1.166

ssh ai-oppo '
echo "=== OPPO ==="
date
pgrep -af runsvdir
SVDIR=$PREFIX/var/service sv status sshd
pgrep -af "sshd -D"
echo "--- boot log ---"
cat ~/worker-boot.log
'
```

Huawei:

```sh
ping -c 3 192.168.1.66

ssh ai-huawei '
echo "=== HUAWEI ==="
date
pgrep -af runsvdir
SVDIR=$PREFIX/var/service sv status sshd
pgrep -af "sshd -D"
echo "--- boot log ---"
cat ~/worker-boot.log
'
```

Critérios de sucesso:

```text
ping responde
      |
      v
runsvdir existe
      |
      v
sv status sshd == run
      |
      v
sshd -D -e existe
      |
      v
SSH funciona sem abrir Termux manualmente
```

Estado em 2026-10-07: **PASSOU nos dois telefones**.

---

## 23. Diagrama do boot final

```text
+------------------+
| Android reboot   |
+--------+---------+
         |
         v
+------------------+
| Termux:Boot      |
| (aberto 1x antes)|
+--------+---------+
         |
         v
+--------------------------+
| ~/.termux/boot/           |
| 00-worker-boot            |
+------------+-------------+
             |
             +--------------------+
             |                    |
             v                    v
   +------------------+    +--------------+
   | termux-wake-lock |    | boot logfile |
   +------------------+    | ~/worker-... |
             |              +--------------+
             v
   +------------------+
   | service-daemon   |
   +--------+---------+
            |
            v
   +------------------+
   | runsvdir         |
   +--------+---------+
            |
            v
   +------------------+
   | runsv sshd       |
   +--------+---------+
            |
            v
   +------------------+
   | sshd -D -e       |
   | TCP 8022         |
   +------------------+
```

---

## 24. Troubleshooting rápido

### 24.1 `Connection refused` na porta 8022

Se ping funciona mas SSH devolve `Connection refused`, a rede está ativa e não existe listener em 8022.

No telefone, se houver acesso local:

```sh
pgrep -af runsvdir
pgrep -af sshd
SVDIR=$PREFIX/var/service sv status sshd
cat ~/worker-boot.log
```

### 24.2 `down: sshd ... want up`

```sh
tail -n 50 "$PREFIX/var/log/sv/sshd/current"
pgrep -af sshd
```

Se aparecer `Address already in use`, procurar daemon manual e fazer a transição controlada descrita na secção 16.

### 24.3 `unable to open supervise/ok`

Depois de instalar `termux-services`, se aparecer:

```text
warning: sshd: unable to open supervise/ok: file does not exist
```

Confirmar que `runsvdir` foi iniciado:

```sh
source "$PREFIX/etc/profile.d/start-services.sh"
sleep 1
pgrep -af runsvdir
```

Ou fechar e reabrir a shell após instalar `termux-services`.

### 24.4 `sv status` falha apenas via `ssh host 'comando'`

Definir `SVDIR` explicitamente:

```sh
SVDIR=$PREFIX/var/service sv status sshd
```

### 24.5 `pkg` diz que nenhum mirror está acessível mas `curl` funciona

```sh
curl -I --max-time 10 \
  https://packages.termux.dev/apt/termux-main/dists/stable/InRelease
```

Se devolver 200, fixar source e usar `apt`:

```sh
echo 'deb https://packages.termux.dev/apt/termux-main stable main' \
  > "$PREFIX/etc/apt/sources.list"

apt update
```

### 24.6 `ss` dá `Cannot open netlink socket: Permission denied`

Pode ocorrer em Android sem root. Usar `pgrep`, `curl`, tentativa de conexão e logs como sinais principais.

### 24.7 SSH tenta porta 22 no PC

O alias `ai-oppo`/`ai-huawei` está configurado no Raspberry. Se o comando for lançado num PC que não tenha o mesmo `~/.ssh/config`, ele pode tentar a porta 22.

Teste explícito:

```sh
ssh -p 8022 u0_a241@192.168.1.166
ssh -p 8022 u0_a192@192.168.1.66
```

---

## 25. Estado atual consolidado

```text
Raspberry Pi
  [OK] plano de controlo físico disponível
  [OK] chave SSH ED25519 própria
  [OK] ~/.ssh/config com ai-oppo / ai-huawei
  [OK] ssh-agent validado
  [OK] acesso SSH aos dois workers

OPPO
  [OK] Termux GitHub 0.119.0-beta.3
  [OK] OpenSSH / porta 8022
  [OK] termux-services / runit
  [OK] sshd supervisionado
  [OK] Termux:Boot
  [OK] 00-worker-boot
  [OK] reboot -> SSH headless
  [OK] llama.cpp compilado
  [OK] Qwen2.5-Coder-1.5B Q4_K_M disponível
  [OK] benchmarks efetuados

Huawei
  [OK] Termux GitHub 0.119.0-beta.3
  [OK] OpenSSH / porta 8022
  [OK] termux-services / runit
  [OK] sshd supervisionado
  [OK] Termux:Boot
  [OK] 00-worker-boot
  [OK] reboot -> SSH headless
  [OK] llama.cpp compilado
  [OK] Qwen2.5-Coder-1.5B Q4_K_M disponível
  [OK] benchmarks efetuados

Rede
  [OK] LAN funcional
  [OK] Tailscale instalado/configurado previamente
  [DECISÃO] Tailscale + MagicDNS será o overlay estável
  [PENDENTE] trocar aliases SSH da LAN para Tailscale/MagicDNS após validação

Inferência
  [OK] llama-server executado/testado manualmente
  [OK] API OpenAI-compatible usada em teste
  [PENDENTE] transformar llama-server em serviço runit
  [PENDENTE] confirmar rejeição de chamadas sem API key
```

---

## 26. Fronteira entre o que existe e o que ainda será desenhado

Este documento fecha a camada de **worker bootstrap + inferência local + SSH headless após reboot**.

Ainda não foi implementado como arquitetura final:

- serviço `runit` do `llama-server`;
- health checks automáticos a partir do Raspberry;
- worker registry persistente;
- scheduler e estado de jobs;
- SQLite do orquestrador;
- protocolo de tarefas/patches;
- worktrees automáticos;
- retrieval por ripgrep/Tree-sitter/LSP;
- aplicação e validação de patches;
- limites/retries/timeouts;
- política de seleção OPPO vs Huawei;
- notificações/approvals (Telegram/ntfy/WhatsApp ainda não decidido);
- isolamento/allowlist de comandos;
- migração definitiva de comunicação para Tailscale/MagicDNS.

Estas decisões devem ser discutidas **depois** deste baseline, sem alterar o bootstrap validado.

---

## 27. Checklist de reinstalação do zero

Use esta ordem:

```text
[ ] 1. Ativar Developer Options + USB debugging
[ ] 2. Confirmar `adb devices`
[ ] 3. Instalar Termux GitHub compatível
[ ] 4. Abrir Termux
[ ] 5. Atualizar apt
[ ] 6. Instalar openssh + build tools
[ ] 7. Criar password temporária se necessária
[ ] 8. Bootstrap SSH por ADB forward:8022
[ ] 9. Confirmar utilizador Termux (`whoami`)
[ ] 10. Passar para SSH direto LAN:8022
[ ] 11. Remover `adb forward`
[ ] 12. Criar/copiar chave SSH do Raspberry
[ ] 13. Criar aliases em ~/.ssh/config
[ ] 14. Instalar termux-services
[ ] 15. Ativar sshd via runit
[ ] 16. Resolver qualquer sshd manual em conflito
[ ] 17. Instalar Termux:Boot da mesma origem
[ ] 18. Abrir Termux:Boot uma vez
[ ] 19. Configurar permissões de bateria/background
[ ] 20. Instalar 00-worker-boot
[ ] 21. Reboot e validar SSH sem abrir Termux
[ ] 22. Avaliar CPU/RAM/clusters
[ ] 23. Compilar llama.cpp em commit registado
[ ] 24. Descarregar GGUF e validar SHA-256
[ ] 25. Executar llama-bench
[ ] 26. Selecionar threads/afinidade por worker
[ ] 27. Criar API key única
[ ] 28. Testar llama-server manualmente
[ ] 29. Confirmar chamada autenticada e rejeição sem token
[ ] 30. Só então criar serviço permanente de inferência
```

---

## 28. Comandos de auditoria do estado atual

### Raspberry

```sh
ssh-add -l

ssh ai-oppo 'date'
ssh ai-huawei 'date'

ssh ai-oppo \
  'pgrep -af runsvdir; SVDIR=$PREFIX/var/service sv status sshd; pgrep -af "sshd -D"'

ssh ai-huawei \
  'pgrep -af runsvdir; SVDIR=$PREFIX/var/service sv status sshd; pgrep -af "sshd -D"'
```

### Worker Android

```sh
termux-info | grep -E 'TERMUX_APP__APK_RELEASE|TERMUX_VERSION'

pgrep -af runsvdir
SVDIR=$PREFIX/var/service sv status sshd
pgrep -af 'sshd -D'

ls -l ~/.termux/boot/00-worker-boot
tail -n 50 ~/worker-boot.log

ls -lh ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
sha256sum ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf

cd ~/llama.cpp
git rev-parse --short HEAD
./build/bin/llama-bench --help | head
./build/bin/llama-server --help | head
```

---

## 29. Referências técnicas

Fontes oficiais/relevantes usadas para validar o procedimento:

- Termux: https://termux.dev/
- Termux app: https://github.com/termux/termux-app
- Termux:Boot: https://github.com/termux/termux-boot
- termux-services: https://github.com/termux/termux-services
- llama.cpp: https://github.com/ggml-org/llama.cpp
- llama-server: https://github.com/ggml-org/llama.cpp/tree/master/tools/server
- Qwen2.5-Coder-1.5B-Instruct-GGUF: https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF
- Tailscale: https://tailscale.com/

---

## 30. Regra operacional daqui para a frente

O baseline considerado estável é:

```text
Android reboot
    -> Termux:Boot
    -> 00-worker-boot
    -> termux-wake-lock
    -> service-daemon
    -> runsvdir
    -> sshd supervisionado
    -> Raspberry entra por SSH
```

Não alterar simultaneamente boot, rede e inferência. A próxima camada deve ser adicionada incrementalmente, começando pelo `llama-server` como serviço supervisionado, mantendo SSH como canal de recuperação independente.
