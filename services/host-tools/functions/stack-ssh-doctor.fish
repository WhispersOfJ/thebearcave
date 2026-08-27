function stack-ssh-doctor --description 'Check SSH config health'
    echo "=== ~/.ssh directory ==="
    if test -d ~/.ssh
        echo "OK"
    else
        echo "MISSING — ~/.ssh does not exist"
    end
    echo ""
    echo "=== GitHub in known_hosts ==="
    if grep -q github.com ~/.ssh/known_hosts 2>/dev/null
        echo "OK"
    else
        echo "MISSING — add with: ssh-keyscan github.com >> ~/.ssh/known_hosts"
    end
    echo ""
    echo "=== Private key ==="
    if test -f ~/.ssh/id_ed25519
        echo "OK (~/.ssh/id_ed25519)"
    else if test -f ~/.ssh/id_rsa
        echo "OK (~/.ssh/id_rsa)"
    else
        echo "MISSING — no private key found"
    end
end
