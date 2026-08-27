function stack-zombie-check --description 'List zombie/defunct processes'
    set -l zombies (ps aux | awk '$8 ~ /Z/ {print}')
    if test -z "$zombies"
        echo "No zombie processes."
    else
        echo "$zombies"
    end
end
