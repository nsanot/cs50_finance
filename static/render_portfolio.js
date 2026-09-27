async function loadPositions() {
    try {
        const response = await fetch('/api/portfolio');

        if (response.ok) {
            const portfolio_info = await response.json();

            document.querySelector('#balance').textContent = portfolio_info.balance;
            document.querySelector('#global_balance').textContent = portfolio_info.global_balance;

            const table = document.querySelector('#positions');
            table.querySelector('#positions_plug').remove();
            for (position of portfolio_info.positions) {
                table.insertAdjacentHTML('beforeend',
                `<tr>
                    <td>${position.stock_symbol}</td>
                    <td>${position.stock_count}</td>
                    <td>${position.stock_price}</td>
                    <td>${position.total_price}</td>
                </tr>`
                );
            }

            if (portfolio_info.positions.length === 0) {
                table.querySelector('#positions_plug').textContent = 'You have no open positions.';
            }
        }
    } catch (error) {
        console.error('Ошибка сети:', error);
    }
}

document.addEventListener('DOMContentLoaded', () => {loadPositions()})
