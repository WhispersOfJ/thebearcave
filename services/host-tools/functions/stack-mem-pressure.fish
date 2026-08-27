function stack-mem-pressure --description 'Kernel PSI for memory, CPU, and IO'
    if test -f /proc/pressure/memory
        echo "=== Memory ==="
        cat /proc/pressure/memory
    else
        echo "PSI not available (kernel < 4.20 or not enabled)"
    end
    if test -f /proc/pressure/cpu
        echo ""
        echo "=== CPU ==="
        cat /proc/pressure/cpu
    end
    if test -f /proc/pressure/io
        echo ""
        echo "=== IO ==="
        cat /proc/pressure/io
    end
end
