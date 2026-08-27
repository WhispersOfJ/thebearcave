#!/usr/bin/env bash
# Secrets management for The Bear Cave setup.
# Sources: scripts/lib/helpers.sh

create_secrets_dir() {
    log_info "Creating secrets directory..."
    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"
    log_success "Secrets directory created"
}

generate_secrets() {
    log_info "Generating Docker secrets..."

    local secrets=(
        "plex_token"
        "radarr_api_key"
        "sonarr_api_key"
        "prowlarr_api_key"
        "tmdb_key"
        "tvdb_key"
        "frontend_backend_api_key"
        "nzbdav_webdav_user"
        "nzbdav_webdav_pass"
        "nzbdav_rclone_rc_pass"
        "nzbdav_profile_token"
        "nzbdav_usenet_host"
        "nzbdav_usenet_user"
        "nzbdav_usenet_pass"
        "nzbdav_usenet_backup_host"
        "nzbdav_usenet_backup_user"
        "nzbdav_usenet_backup_pass"
        "ws_api_key"
        "ws_system_secret"
        "metacache_api_key"
        "discord_webhook_url"
        "omdb_key"
        "mdblist_key"
        "fanart_key"
        "grafana_admin_password"
    )

    for secret in "${secrets[@]}"; do
        local secret_file="$SECRETS_DIR/$secret"

        if [ ! -f "$secret_file" ]; then
            local value
            value=$(generate_secret 32)
            echo -n "$value" > "$secret_file"
            chmod 600 "$secret_file"
            log_info "Generated secret: $secret"
        else
            log_info "Secret already exists: $secret"
        fi
    done

    log_success "All secrets generated"
}
