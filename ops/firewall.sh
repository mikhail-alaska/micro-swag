#!/bin/sh
set -eu

chain=MICRO_SWAG

cache_rule() {
    iptables -w "$@" "$chain" -s 172.30.30.10 -d 172.30.30.20 \
        -p tcp --dport 6379 -m comment --comment micro-swag-demo-cache \
        -j REJECT --reject-with tcp-reset
}

case "${1:-show}" in
    apply)
        if ! iptables -w -S DOCKER-USER >/dev/null 2>&1 || ! iptables -w -C FORWARD -j DOCKER-USER 2>/dev/null; then
            printf 'This firewall requires rootful Docker Engine with the iptables firewall backend\n' >&2
            exit 1
        fi
        wan_interface=${2:-}
        if [ -z "$wan_interface" ]; then
            wan_interface=$(ip -4 route show default | awk 'NR == 1 {for (i = 1; i <= NF; i++) if ($i == "dev") {print $(i + 1); exit}}')
        fi
        case "$wan_interface" in
            ''|*[!a-zA-Z0-9_.:-]*)
                printf 'Cannot detect the external interface; pass its name after apply\n' >&2
                exit 1
                ;;
        esac
        ip link show dev "$wan_interface" >/dev/null

        # Иначе пакеты внутри одного bridge могут обходить IP firewall.
        modprobe br_netfilter
        sysctl -q -w net.bridge.bridge-nf-call-iptables=1

        # Меняем только свою цепочку; остальные правила Docker сохраняются.
        iptables-restore --wait 5 --noflush <<RULES
*filter
:MICRO_SWAG - [0:0]
-F MICRO_SWAG
-A MICRO_SWAG -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Nginx -> API; API -> CVE; CVE -> Redis.
-A MICRO_SWAG -s 172.30.10.10 -d 172.30.10.20 -p tcp --dport 8000 -j ACCEPT
-A MICRO_SWAG -s 172.30.20.10 -d 172.30.20.20 -p tcp --dport 8000 -j ACCEPT
-A MICRO_SWAG -s 172.30.30.10 -d 172.30.30.20 -p tcp --dport 6379 -j ACCEPT

# API и worker -> оба узла PostgreSQL; репликация в обе стороны.
-A MICRO_SWAG -s 172.30.40.10 -d 172.30.40.30 -p tcp --dport 5432 -j ACCEPT
-A MICRO_SWAG -s 172.30.40.10 -d 172.30.40.40 -p tcp --dport 5432 -j ACCEPT
-A MICRO_SWAG -s 172.30.40.20 -d 172.30.40.30 -p tcp --dport 5432 -j ACCEPT
-A MICRO_SWAG -s 172.30.40.20 -d 172.30.40.40 -p tcp --dport 5432 -j ACCEPT
-A MICRO_SWAG -s 172.30.40.30 -d 172.30.40.40 -p tcp --dport 5432 -j ACCEPT
-A MICRO_SWAG -s 172.30.40.40 -d 172.30.40.30 -p tcp --dport 5432 -j ACCEPT

# API/worker -> HAProxy -> RabbitMQ.
-A MICRO_SWAG -s 172.30.50.10 -d 172.30.50.30 -p tcp --dport 5672 -j ACCEPT
-A MICRO_SWAG -s 172.30.50.20 -d 172.30.50.30 -p tcp --dport 5672 -j ACCEPT
-A MICRO_SWAG -s 172.30.50.30 -d 172.30.50.41 -p tcp --dport 5672 -j ACCEPT
-A MICRO_SWAG -s 172.30.50.30 -d 172.30.50.42 -p tcp --dport 5672 -j ACCEPT
-A MICRO_SWAG -s 172.30.50.30 -d 172.30.50.43 -p tcp --dport 5672 -j ACCEPT

# Erlang discovery и соединения между тремя узлами кластера.
-A MICRO_SWAG -m iprange --src-range 172.30.50.41-172.30.50.43 -m iprange --dst-range 172.30.50.41-172.30.50.43 -p tcp -m multiport --dports 4369,25672 -j ACCEPT

# Скрипт проверки лидера читает management API с backend.
-A MICRO_SWAG -s 172.30.50.10 -m iprange --dst-range 172.30.50.41-172.30.50.43 -p tcp --dport 15672 -j ACCEPT
-A MICRO_SWAG -s 172.30.50.30 -m iprange --dst-range 172.30.50.41-172.30.50.43 -p tcp --dport 15672 -j ACCEPT

# Публикуемые порты: вход с внешнего интерфейса и bridge gateway.
-A MICRO_SWAG -i $wan_interface -d 172.30.10.10 -p tcp --dport 80 -j ACCEPT
-A MICRO_SWAG -i $wan_interface -d 172.30.10.20 -p tcp --dport 8000 -j ACCEPT
-A MICRO_SWAG -i $wan_interface -d 172.30.20.20 -p tcp --dport 8000 -j ACCEPT
-A MICRO_SWAG -i $wan_interface -d 172.30.10.30 -p tcp -m multiport --dports 15672,15673,15674 -j ACCEPT
-A MICRO_SWAG -s 172.30.10.1 -d 172.30.10.10 -p tcp --dport 80 -j ACCEPT
-A MICRO_SWAG -s 172.30.10.1 -d 172.30.10.20 -p tcp --dport 8000 -j ACCEPT
-A MICRO_SWAG -s 172.30.20.1 -d 172.30.20.20 -p tcp --dport 8000 -j ACCEPT
-A MICRO_SWAG -s 172.30.10.1 -d 172.30.10.30 -p tcp -m multiport --dports 15672,15673,15674 -j ACCEPT

# Только CVE-сервису нужен внешний HTTPS. DNS обслуживает Docker.
-A MICRO_SWAG -s 172.30.20.20 ! -d 172.30.0.0/16 -p tcp --dport 443 -j ACCEPT

-A MICRO_SWAG -p tcp -j REJECT --reject-with tcp-reset
-A MICRO_SWAG -j REJECT --reject-with icmp-port-unreachable
COMMIT
RULES
        for subnet in 10 20 30 40 50; do
            for direction in -s -d; do
                if ! iptables -w -C DOCKER-USER "$direction" "172.30.$subnet.0/24" -j "$chain" 2>/dev/null; then
                    iptables -w -I DOCKER-USER 1 "$direction" "172.30.$subnet.0/24" -j "$chain"
                fi
            done
        done
        printf 'Firewall applied to the five micro-swag subnets; external interface: %s\n' "$wan_interface"
        ;;
    show)
        iptables -w -S DOCKER-USER
        iptables -w -nvL "$chain" --line-numbers
        ;;
    save)
        iptables-save
        ;;
    block-cache)
        if ! cache_rule -C 2>/dev/null; then
            cache_rule -I
        fi
        printf 'CVE -> Redis blocked, including existing connections\n'
        ;;
    unblock-cache)
        if cache_rule -C 2>/dev/null; then
            cache_rule -D
        fi
        printf 'CVE -> Redis restored\n'
        ;;
    remove)
        for subnet in 10 20 30 40 50; do
            for direction in -s -d; do
                while iptables -w -C DOCKER-USER "$direction" "172.30.$subnet.0/24" -j "$chain" 2>/dev/null; do
                    iptables -w -D DOCKER-USER "$direction" "172.30.$subnet.0/24" -j "$chain"
                done
            done
        done
        if iptables -w -S "$chain" >/dev/null 2>&1; then
            iptables -w -F "$chain"
            iptables -w -X "$chain"
        fi
        printf 'Only micro-swag firewall rules removed\n'
        ;;
    *)
        printf 'Usage: firewall.sh apply|show|save|block-cache|unblock-cache|remove\n' >&2
        exit 1
        ;;
esac
