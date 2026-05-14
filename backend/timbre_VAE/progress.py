
import time


def clear_lines(n=1)-> None:
    """Clears the last n lines in the console."""
    LINE_UP = '\033[F'  # Move cursor up one line
    LINE_CLEAR = '\033[K'  # Clear to the end of line
    for idx in range(n):
        print(LINE_UP, end=LINE_CLEAR)
    return


def increment_progress_bar(current, total, description='', bar_length=40):
    percent = float(current) / total
    arrow = '*' * int(round(percent * bar_length)-1) + '>'
    spaces = ' ' * (bar_length - len(arrow))
    # print('.')
    print(f'{description}: [{arrow}{spaces}] {int(round(percent * 100))}%')



#EG
#tqdm(range(epochs), desc="Training VAE", unit="epoch", ncols=80):


# Test

total_epochs = 100
for epoch in range(total_epochs):
    increment_progress_bar(epoch + 1, total_epochs, description="Training VAE") 
    # Simulate work being done
    clear_lines()