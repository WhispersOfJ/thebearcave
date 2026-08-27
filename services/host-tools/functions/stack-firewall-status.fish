function stack-firewall-status --description 'Active nftables rules + listening ports'
    echo "=== Listening Ports ==="
    ss -tlnp 2>/dev/null | head -30
    echo ""
    echo "=== nftables ==="
    sudo nft list ruleset 2>/dev/null | head -30 || echo "nft not available"
end
