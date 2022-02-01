gpio -g write 4 1
while :
do
    # ON
    gpio -g write 12 0
    gpio -g write 22 0
    gpio -g write 23 0

    # SLEEP
    sleep 4
    # OFF
    gpio -g write 22 1
    # SLEEP
    sleep 5
    gpio -g write 23 1
    sleep 1
done
